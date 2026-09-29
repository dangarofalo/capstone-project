"""Reads the Linux authentication log (/var/log/auth.log or /var/log/secure)."""
import os
import re
from datetime import datetime, timezone

from .state import load_state, save_state

PATTERNS = [
    ("login_failure", re.compile(r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>\S+)")),
    ("login_success", re.compile(r"Accepted (?:password|publickey|keyboard-interactive/pam) for (?P<user>\S+) from (?P<ip>\S+)")),
    ("account_created", re.compile(r"new user: name=(?P<user>[^,\s]+)")),
    ("admin_group_added", re.compile(r"add '(?P<user>[^']+)' to group '(?P<group>sudo|wheel|admin)'")),
]

# Newer distros: "2026-09-29T14:03:11.123456+00:00 host sshd[99]: ..."
ISO_LINE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\S+)\s+(?P<host>\S+)\s+(?P<msg>.*)$")
# Classic syslog: "Sep 29 14:03:11 host sshd[99]: ..." (no year, local time)
SYSLOG_LINE = re.compile(r"^(?P<ts>[A-Z][a-z]{2}\s+\d{1,2} \d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<msg>.*)$")


def _parse_timestamp(line: str, now: datetime) -> tuple[datetime, str] | None:
    if m := ISO_LINE.match(line):
        ts = datetime.fromisoformat(m["ts"])
        if ts.tzinfo is None:
            ts = ts.astimezone()
        return ts.astimezone(timezone.utc), m["msg"]
    if m := SYSLOG_LINE.match(line):
        local = datetime.strptime(f"{now.year} {m['ts']}", "%Y %b %d %H:%M:%S").astimezone()
        if local > now.astimezone() and (local - now.astimezone()).days >= 1:
            local = local.replace(year=now.year - 1)  # a December line read in January
        return local.astimezone(timezone.utc), m["msg"]
    return None


def parse_line(line: str, record_id: str, now: datetime | None = None) -> dict | None:
    """Turn one auth.log line into an API event, or None if it is not interesting."""
    parsed = _parse_timestamp(line.strip(), now or datetime.now(timezone.utc))
    if parsed is None:
        return None
    event_time, message = parsed
    for event_type, pattern in PATTERNS:
        if m := pattern.search(message):
            return {
                "record_id": record_id,
                "event_time": event_time.isoformat(),
                "event_type": event_type,
                "username": m["user"],
                "source_ip": m.groupdict().get("ip"),
                "logon_type": "ssh" if "sshd" in message else None,
                "source_event_id": None,
                "message": message[:2000],
            }
    return None


class LinuxCollector:
    def __init__(self, config: dict):
        self.state_file = config.get("state_file", "agent_state.json")
        self.path = config.get("linux_log_path") or (
            "/var/log/auth.log" if os.path.exists("/var/log/auth.log") else "/var/log/secure"
        )
        self.state = load_state(self.state_file)
        self._pending: dict | None = None

    def collect(self) -> list[dict]:
        stat = os.stat(self.path)
        offset = self.state.get("linux_offset", 0)
        # Start over if the log was rotated (new file) or truncated.
        if self.state.get("linux_inode") != stat.st_ino or stat.st_size < offset:
            offset = 0

        events = []
        with open(self.path, "rb") as f:
            f.seek(offset)
            while True:
                line_start = f.tell()
                raw = f.readline()
                if not raw or not raw.endswith(b"\n"):
                    break  # stop at a half-written last line; read it next time
                offset = f.tell()
                record_id = f"{stat.st_ino}:{line_start}"
                event = parse_line(raw.decode("utf-8", errors="replace"), record_id)
                if event:
                    events.append(event)

        self._pending = {"linux_inode": stat.st_ino, "linux_offset": offset}
        return events

    def commit(self) -> None:
        if self._pending:
            self.state.update(self._pending)
            save_state(self.state_file, self.state)
            self._pending = None
