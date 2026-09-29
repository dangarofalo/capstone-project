"""Reads the Windows Security Event Log using the built-in wevtutil tool.

Reading the Security log requires running the agent as Administrator.
"""
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .state import load_state, save_state

NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}

# Windows event ID -> SentinelView event type
EVENT_TYPES = {
    4624: "login_success",
    4625: "login_failure",
    4720: "account_created",
    4728: "admin_group_added",  # member added to a global group
    4732: "admin_group_added",  # member added to a local group
    4756: "admin_group_added",  # member added to a universal group
    4740: "account_lockout",
}

# Group-membership events are only interesting when the group grants admin rights.
ADMIN_GROUPS = {"administrators", "domain admins", "enterprise admins", "schema admins"}

# Logon types a person causes: 2 console, 3 network, 7 unlock, 10 remote desktop, 11 cached.
# Others (4 batch, 5 service) are background noise from Windows itself.
HUMAN_LOGON_TYPES = {"2", "3", "7", "10", "11"}

SYSTEM_ACCOUNTS = {"system", "local service", "network service", "anonymous logon", "-", ""}

LOCAL_ADDRESSES = {"-", "", "127.0.0.1", "::1"}


def _parse_time(value: str) -> datetime:
    # Windows writes 7 fractional digits ("...:03.1234567Z"); Python accepts at most 6.
    main, _, rest = value.rstrip("Z").partition(".")
    fraction = rest[:6] if rest else "0"
    return datetime.fromisoformat(f"{main}.{fraction}").replace(tzinfo=timezone.utc)


def _is_system_account(name: str) -> bool:
    lower = name.lower()
    return (
        lower in SYSTEM_ACCOUNTS
        or lower.endswith("$")  # computer accounts
        or lower.startswith(("dwm-", "umfd-"))  # desktop window manager / font driver
    )


def parse_event(event: ET.Element) -> tuple[int, dict | None]:
    """Turn one <Event> element into (record_id, api_event). api_event is None if skipped."""
    system = event.find("e:System", NS)
    record_id = int(system.findtext("e:EventRecordID", "0", NS))
    event_id = int(system.findtext("e:EventID", "0", NS))
    created = system.find("e:TimeCreated", NS).get("SystemTime")
    data = {
        d.get("Name"): (d.text or "").strip()
        for d in event.findall("e:EventData/e:Data", NS)
    }

    event_type = EVENT_TYPES.get(event_id)
    if event_type is None:
        return record_id, None

    username = data.get("TargetUserName", "")
    source_ip = data.get("IpAddress", "")
    logon_type = data.get("LogonType") or None

    if event_id == 4624:
        if logon_type not in HUMAN_LOGON_TYPES or _is_system_account(username):
            return record_id, None
        if logon_type == "3" and source_ip in LOCAL_ADDRESSES:
            return record_id, None  # the machine talking to itself
        message = f"{username} logged on (type {logon_type})"
    elif event_id == 4625:
        message = f"Failed logon for {username or 'unknown user'} (type {logon_type})"
    elif event_id == 4720:
        message = f"User account {username} was created by {data.get('SubjectUserName', '?')}"
    elif event_id in (4728, 4732, 4756):
        group = username  # for these events TargetUserName is the group
        if group.lower() not in ADMIN_GROUPS:
            return record_id, None
        username = data.get("MemberName") or data.get("MemberSid", "")
        message = f"{username} was added to {group} by {data.get('SubjectUserName', '?')}"
    else:  # 4740
        message = f"Account {username} was locked out (caller: {data.get('TargetDomainName', '?')})"

    return record_id, {
        "record_id": str(record_id),
        "event_time": _parse_time(created).isoformat(),
        "event_type": event_type,
        "username": username or None,
        "source_ip": None if source_ip in LOCAL_ADDRESSES else source_ip,
        "logon_type": logon_type,
        "source_event_id": str(event_id),
        "message": message[:2000],
    }


def parse_events_xml(xml_text: str) -> tuple[list[dict], int]:
    """Parse wevtutil output. Returns (api_events, highest_record_id_seen)."""
    root = ET.fromstring(f"<Events>{xml_text}</Events>")
    events, max_record = [], 0
    for element in root.findall("e:Event", NS):
        record_id, api_event = parse_event(element)
        max_record = max(max_record, record_id)
        if api_event:
            events.append(api_event)
    return events, max_record


def build_query(last_record_id: int | None, lookback_hours: int) -> str:
    ids = " or ".join(f"EventID={i}" for i in EVENT_TYPES)
    if last_record_id is None:
        since = f"TimeCreated[timediff(@SystemTime) <= {lookback_hours * 3600 * 1000}]"
    else:
        since = f"EventRecordID > {last_record_id}"
    return f"*[System[({ids}) and {since}]]"


class WindowsCollector:
    def __init__(self, config: dict):
        self.state_file = config.get("state_file", "agent_state.json")
        self.lookback_hours = int(config.get("initial_lookback_hours", 24))
        self.max_events = int(config.get("max_events_per_run", 2000))
        self.state = load_state(self.state_file)
        self._pending_record_id: int | None = None

    def collect(self) -> list[dict]:
        last = self.state.get("windows_last_record_id")
        cmd = [
            "wevtutil", "qe", "Security",
            f"/q:{build_query(last, self.lookback_hours)}",
            "/f:xml", f"/c:{self.max_events}", "/rd:false",  # oldest first
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            error = result.stderr.decode(errors="replace").strip()
            if result.returncode == 5 or "access is denied" in error.lower():
                raise PermissionError(
                    "Access denied reading the Security log. Run the agent as Administrator."
                )
            raise RuntimeError(f"wevtutil failed ({result.returncode}): {error}")

        raw = result.stdout
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("mbcs", errors="replace")

        events, max_record = parse_events_xml(text)
        if max_record:
            self._pending_record_id = max_record
        return events

    def commit(self) -> None:
        if self._pending_record_id is not None:
            self.state["windows_last_record_id"] = self._pending_record_id
            save_state(self.state_file, self.state)
            self._pending_record_id = None
