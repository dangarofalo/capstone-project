"""Send realistic fake security events to SentinelView for testing and demos.

Each scenario is designed to trip one detection rule (normal raises none).
Nothing is attacked: this only posts made-up events to your own server's API,
so you can test without Administrator rights or a real attack.

    python scripts/simulate_events.py --api-key sv_xxx
    python scripts/simulate_events.py --api-key sv_xxx --scenario brute-force --host LAB-PC-02
"""
import argparse
import json
import random
import sys
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

USERS = ["alice", "bob", "carol", "dave", "admin"]
ATTACKER_IPS = ["203.0.113.45", "198.51.100.23", "192.0.2.77"]
OFFICE_IPS = ["10.0.0.12", "10.0.0.15", "10.0.0.21"]


def event(event_type, when, username, source_ip=None, logon_type="3", message=""):
    return {
        "record_id": f"sim-{uuid.uuid4().hex[:16]}",
        "event_time": when.isoformat(),
        "event_type": event_type,
        "username": username,
        "source_ip": source_ip,
        "logon_type": logon_type,
        "source_event_id": {"login_success": "4624", "login_failure": "4625", "account_created": "4720",
                            "admin_group_added": "4732", "account_lockout": "4740"}[event_type],
        "message": message or f"[simulated] {event_type} for {username}",
    }


def business_hours_yesterday(now):
    """A random time between 8 AM and 6 PM yesterday, in this computer's time zone."""
    local = now.astimezone() - timedelta(days=1)
    return local.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(minutes=random.uniform(0, 600))


def normal_day(now):
    """A day of ordinary office logins with the occasional typo. Should raise no alerts."""
    events = []
    for _ in range(40):
        when = business_hours_yesterday(now)
        user = random.choice(USERS[:4])
        if random.random() < 0.1:
            events.append(event("login_failure", when, user, random.choice(OFFICE_IPS), "2"))
        events.append(event("login_success", when + timedelta(seconds=5), user, random.choice(OFFICE_IPS), "2"))
    return events


def brute_force(now):
    """Many failed logins from one outside IP in a few minutes, ending in a lockout."""
    ip, user = random.choice(ATTACKER_IPS), "admin"
    start = now - timedelta(minutes=4)
    events = [
        event("login_failure", start + timedelta(seconds=i * 12), user, ip, "3", f"[simulated] Failed logon for {user} from {ip}")
        for i in range(15)
    ]
    events.append(event("account_lockout", start + timedelta(minutes=3, seconds=5), user, None, None, f"[simulated] Account {user} was locked out"))
    return events


def privilege_escalation(now):
    """A new account is created and quickly added to Administrators."""
    return [
        event("account_created", now - timedelta(minutes=2), "svc_backup2", None, None, "[simulated] User account svc_backup2 was created by bob"),
        event("admin_group_added", now - timedelta(minutes=1), "svc_backup2", None, None, "[simulated] svc_backup2 was added to Administrators by bob"),
    ]


def off_hours(now):
    """A remote desktop login at 3 AM (this computer's time zone)."""
    night = (now.astimezone() - timedelta(days=1)).replace(hour=3, minute=12, second=0, microsecond=0)
    return [event("login_success", night, "carol", random.choice(ATTACKER_IPS), "10", "[simulated] carol logged on via Remote Desktop")]


SCENARIOS = {
    "normal": normal_day,
    "brute-force": brute_force,
    "privilege-escalation": privilege_escalation,
    "off-hours": off_hours,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api-key", required=True, help="key from: python -m app.manage create-agent NAME")
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--host", default="SIM-PC-01", help="hostname to report the events under")
    parser.add_argument("--scenario", choices=[*SCENARIOS, "all"], default="all")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    events = [e for name in names for e in SCENARIOS[name](now)]

    request = urllib.request.Request(
        args.server.rstrip("/") + "/api/ingest/events",
        data=json.dumps({"hostname": args.host, "os": "Simulated", "events": events}).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": args.api_key},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.loads(response.read())
    print(f"Scenarios: {', '.join(names)} -> {result['accepted']} events stored for host {args.host}, "
          f"{result.get('alerts_created', 0)} new alerts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
