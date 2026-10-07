"""Detection rules: turn raw events into alerts a non-expert can act on.

Event rules run on each batch as it is stored. The offline-agent rule runs on a
timer instead, because it looks for events that did *not* arrive.

Rule               Severity  Fires when
brute_force        high      >= BRUTE_FORCE_THRESHOLD failed logins from one IP (or for one
                             user, if no IP) on one host within BRUTE_FORCE_WINDOW_MINUTES
admin_added        high      an account is added to an administrator group
off_hours_login    medium    a person logs in interactively outside business hours
agent_offline      medium    an agent has not reported for AGENT_OFFLINE_MINUTES
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .models import Agent, Alert, Event, utcnow

ACTIVE_STATUSES = ("open", "acknowledged")

# Console, unlock, remote desktop, cached, and SSH logins. Network logons (type 3)
# are mostly file shares and printers, which would make this rule too noisy.
INTERACTIVE_LOGON_TYPES = {"2", "7", "10", "11", "ssh"}


def _find_active(db: Session, dedup_key: str) -> Alert | None:
    return db.scalar(
        select(Alert)
        .where(Alert.dedup_key == dedup_key, Alert.status.in_(ACTIVE_STATUSES))
        .order_by(Alert.id.desc())
    )


def _new_alert(db: Session, **fields) -> Alert:
    alert = Alert(status="open", **fields)
    db.add(alert)
    db.flush()  # so the next lookup in this batch can find it
    return alert


def _fmt_list(items: list[str], limit: int = 3) -> str:
    shown = ", ".join(f"'{i}'" for i in items[:limit])
    return shown + (f" and {len(items) - limit} more" if len(items) > limit else "")


def _local_time(utc_naive: datetime) -> datetime:
    tz = ZoneInfo(config.TIMEZONE) if config.TIMEZONE else None  # None = server's zone
    return utc_naive.replace(tzinfo=timezone.utc).astimezone(tz)


# --- Event rules ------------------------------------------------------------


def _brute_force(db: Session, event: Event, created: list[Alert]) -> None:
    window_start = event.event_time - timedelta(minutes=config.BRUTE_FORCE_WINDOW_MINUTES)
    query = select(Event).where(
        Event.host == event.host,
        Event.event_type == "login_failure",
        Event.event_time > window_start,
        Event.event_time <= event.event_time,
    )
    # Group by attacker IP when we know it; otherwise by the account being attacked.
    if event.source_ip:
        query = query.where(Event.source_ip == event.source_ip)
        key = f"brute_force:{event.host}:ip:{event.source_ip}"
    else:
        query = query.where(Event.username == event.username)
        key = f"brute_force:{event.host}:user:{event.username}"

    failures = db.scalars(query).all()
    if len(failures) < config.BRUTE_FORCE_THRESHOLD:
        return

    alert = _find_active(db, key)
    if alert is None:
        alert = _new_alert(
            db,
            rule="brute_force",
            severity="high",
            dedup_key=key,
            host=event.host,
            source_ip=event.source_ip,
            first_seen=failures[0].event_time,
            last_seen=event.event_time,
            title="",
            description="",
            recommendation="",
        )
        created.append(alert)

    for failure in failures:
        if failure not in alert.events:
            alert.events.append(failure)
    alert.event_count = len(alert.events)
    alert.first_seen = min(alert.first_seen, *(e.event_time for e in failures))
    alert.last_seen = max(alert.last_seen, event.event_time)

    users = sorted({e.username for e in alert.events if e.username})
    alert.username = users[0] if len(users) == 1 else None
    origin = f"from {alert.source_ip}" if alert.source_ip else "from an unknown address"
    target = f"account {_fmt_list(users)}" if users else "an unknown account"

    alert.title = f"Possible password-guessing attack on {alert.host}"
    alert.description = (
        f"{alert.event_count} failed logins to {target} {origin}. At least "
        f"{config.BRUTE_FORCE_THRESHOLD} happened within {config.BRUTE_FORCE_WINDOW_MINUTES} "
        "minutes, which usually means a program is guessing passwords rather than a "
        "person making typos."
    )
    alert.recommendation = (
        (f"Check whether {alert.source_ip} is an address you recognize. If not, block it at "
         "your firewall. " if alert.source_ip else "")
        + "Make sure the targeted account has a strong, unique password, turn on account "
        "lockout after a few failed attempts, and confirm there was no successful login "
        "from the same source afterwards."
    )


def _admin_added(db: Session, event: Event, created: list[Alert]) -> None:
    alert = _new_alert(
        db,
        rule="admin_added",
        severity="high",
        dedup_key=f"admin_added:{event.id}",
        host=event.host,
        username=event.username,
        first_seen=event.event_time,
        last_seen=event.event_time,
        event_count=1,
        title=f"New administrator on {event.host}: {event.username or 'unknown account'}",
        description=(
            f"{(event.message or 'An account was added to an administrator group').rstrip('.')}. "
            "Administrators have full control of the computer, and attackers often create "
            "or promote an account so they can get back in later."
        ),
        recommendation=(
            "Confirm with your team that this change was planned. If nobody recognizes it, "
            "remove the account from the administrator group, disable it, and check which "
            "account made the change for other suspicious activity."
        ),
    )
    alert.events.append(event)
    created.append(alert)


def _off_hours_login(db: Session, event: Event, created: list[Alert]) -> None:
    if event.logon_type not in INTERACTIVE_LOGON_TYPES:
        return
    local = _local_time(event.event_time)
    if config.WORK_HOURS_START <= local.hour < config.WORK_HOURS_END:
        return

    how = "via Remote Desktop" if event.logon_type == "10" else "via SSH" if event.logon_type == "ssh" else ""
    origin = f" from {event.source_ip}" if event.source_ip else ""
    alert = _new_alert(
        db,
        rule="off_hours_login",
        severity="medium",
        dedup_key=f"off_hours_login:{event.id}",
        host=event.host,
        username=event.username,
        source_ip=event.source_ip,
        first_seen=event.event_time,
        last_seen=event.event_time,
        event_count=1,
        title=f"After-hours login by {event.username or 'unknown user'} on {event.host}",
        description=(
            f"{event.username or 'Someone'} logged in {how}{origin} at "
            f"{local:%I:%M %p on %a %b %d} (local time), outside business hours "
            f"({config.WORK_HOURS_START}:00 to {config.WORK_HOURS_END}:00)."
        ).replace("  ", " "),
        recommendation=(
            "Ask the user whether this was them. If it was not, change their password "
            "right away and check what the account did after logging in."
        ),
    )
    alert.events.append(event)
    created.append(alert)


EVENT_RULES = {
    "login_failure": _brute_force,
    "admin_group_added": _admin_added,
    "login_success": _off_hours_login,
}


def run_event_rules(db: Session, events: list[Event]) -> list[Alert]:
    """Check newly stored events (already flushed) and return any alerts created."""
    created: list[Alert] = []
    for event in sorted(events, key=lambda e: e.event_time):
        rule = EVENT_RULES.get(event.event_type)
        if rule:
            rule(db, event, created)
    return created


# --- Offline agents -----------------------------------------------------------


def _offline_key(agent: Agent) -> str:
    return f"agent_offline:{agent.id}"


def check_offline_agents(db: Session, now: datetime | None = None) -> list[Alert]:
    """Raise one alert per agent that has gone quiet. Commits and returns new alerts."""
    now = now or utcnow()
    cutoff = now - timedelta(minutes=config.AGENT_OFFLINE_MINUTES)
    quiet = db.scalars(
        select(Agent).where(Agent.last_seen.is_not(None), Agent.last_seen < cutoff)
    ).all()

    created = []
    for agent in quiet:
        if _find_active(db, _offline_key(agent)):
            continue
        host = agent.hostname or agent.name
        minutes = int((now - agent.last_seen).total_seconds() // 60)
        created.append(
            _new_alert(
                db,
                rule="agent_offline",
                severity="medium",
                dedup_key=_offline_key(agent),
                host=host,
                agent_id=agent.id,
                first_seen=agent.last_seen,
                last_seen=agent.last_seen,
                title=f"{host} stopped reporting",
                description=(
                    f"The SentinelView agent on {host} has not checked in for {minutes} "
                    "minutes. While it is offline, attacks on this computer will not be seen. "
                    "Attackers sometimes stop security software first."
                ),
                recommendation=(
                    "Check that the computer is turned on and connected to the network, and "
                    "that the agent is still running. Restart it if needed. This alert "
                    "resolves itself when the agent reports again."
                ),
            )
        )
    db.commit()
    return created


def resolve_offline_alert(db: Session, agent: Agent, now: datetime) -> None:
    """Called when an agent reports in: close its offline alert if it has one."""
    alert = _find_active(db, _offline_key(agent))
    if alert:
        alert.status = "resolved"
        alert.resolved_at = now
        alert.resolution_note = "Resolved automatically: the agent reported again."
