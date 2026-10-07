from datetime import datetime, timedelta

import pytest

from app import config, notifications
from app.detection import check_offline_agents
from app.models import Agent, Alert, utcnow

BASE = datetime(2026, 10, 6, 14, 0, 0)  # a Tuesday, 2 PM UTC (business hours)


@pytest.fixture(autouse=True)
def fixed_business_hours(monkeypatch):
    """Make the off-hours rule independent of this computer's time zone."""
    monkeypatch.setattr(config, "TIMEZONE", "UTC")
    monkeypatch.setattr(config, "WORK_HOURS_START", 7)
    monkeypatch.setattr(config, "WORK_HOURS_END", 19)


_record = iter(range(1, 10_000))


def ev(event_type, when, username="admin", source_ip="203.0.113.45", logon_type="3", **extra):
    return {
        "record_id": str(next(_record)),
        "event_time": when.isoformat() + "Z",
        "event_type": event_type,
        "username": username,
        "source_ip": source_ip,
        "logon_type": logon_type,
        **extra,
    }


def failures(count, start=BASE, every_seconds=10, **kw):
    return [ev("login_failure", start + timedelta(seconds=i * every_seconds), **kw) for i in range(count)]


def send(client, api_key, events, hostname="PC-01"):
    resp = client.post(
        "/api/ingest/events",
        json={"hostname": hostname, "events": events},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def alerts(client, **params):
    return client.get("/api/alerts", params=params).json()["items"]


# --- Brute force ---------------------------------------------------------------


def test_four_failures_is_not_an_attack(client, api_key):
    assert send(client, api_key, failures(4))["alerts_created"] == 0
    assert alerts(client) == []


def test_five_failures_in_five_minutes_raises_high_alert(client, api_key):
    assert send(client, api_key, failures(5))["alerts_created"] == 1
    [alert] = alerts(client)
    assert alert["rule"] == "brute_force"
    assert alert["severity"] == "high"
    assert alert["status"] == "open"
    assert alert["event_count"] == 5
    assert alert["source_ip"] == "203.0.113.45"
    assert alert["username"] == "admin"
    assert "203.0.113.45" in alert["recommendation"]


def test_failures_spread_out_do_not_trigger(client, api_key):
    send(client, api_key, failures(6, every_seconds=90))  # 6 failures over 7.5 minutes
    assert alerts(client) == []


def test_continuing_attack_updates_the_same_alert(client, api_key):
    send(client, api_key, failures(5))
    later = send(client, api_key, failures(10, start=BASE + timedelta(minutes=1)))
    assert later["alerts_created"] == 0
    [alert] = alerts(client)
    assert alert["event_count"] == 15


def test_attack_after_resolving_creates_new_alert(client, api_key):
    send(client, api_key, failures(5))
    alert_id = alerts(client)[0]["id"]
    client.post(f"/api/alerts/{alert_id}/resolve", json={"note": "blocked IP"})
    send(client, api_key, failures(5, start=BASE + timedelta(hours=1)))
    assert len(alerts(client, status="open")) == 1
    assert len(alerts(client)) == 2


def test_different_ips_are_separate_alerts(client, api_key):
    send(client, api_key, failures(5, source_ip="203.0.113.1") + failures(5, source_ip="203.0.113.2"))
    assert len(alerts(client)) == 2


def test_password_spraying_from_one_ip_lists_all_users(client, api_key):
    events = [ev("login_failure", BASE + timedelta(seconds=i), username=u) for i, u in enumerate(["a", "b", "c", "d", "e"])]
    send(client, api_key, events)
    [alert] = alerts(client)
    assert alert["username"] is None  # several accounts were targeted
    assert "'a', 'b', 'c' and 2 more" in alert["description"]


def test_no_ip_groups_by_username(client, api_key):
    send(client, api_key, failures(5, source_ip=None, username="bob", logon_type="2"))
    [alert] = alerts(client)
    assert alert["username"] == "bob" and alert["source_ip"] is None


# --- Admin added / off-hours ----------------------------------------------------


def test_admin_group_add_raises_high_alert(client, api_key):
    send(client, api_key, [ev("admin_group_added", BASE, username="svc_backup2", source_ip=None,
                              message="svc_backup2 was added to Administrators by bob")])
    [alert] = alerts(client)
    assert (alert["rule"], alert["severity"]) == ("admin_added", "high")
    assert "svc_backup2" in alert["title"]
    assert "by bob. Administrators have full control" in alert["description"]


def test_remote_login_at_3am_is_off_hours(client, api_key):
    send(client, api_key, [ev("login_success", BASE.replace(hour=3), username="carol", logon_type="10")])
    [alert] = alerts(client)
    assert (alert["rule"], alert["severity"]) == ("off_hours_login", "medium")
    assert "Remote Desktop" in alert["description"]


def test_business_hours_and_network_logins_are_ignored(client, api_key):
    send(client, api_key, [
        ev("login_success", BASE.replace(hour=10), logon_type="2"),  # daytime console login
        ev("login_success", BASE.replace(hour=3), logon_type="3"),   # 3 AM file-share access
        ev("login_success", BASE.replace(hour=19), logon_type="2"),  # 7 PM is after hours...
    ])
    assert [a["rule"] for a in alerts(client)] == ["off_hours_login"]  # ...so only that one


def test_respects_configured_time_zone(client, api_key, monkeypatch):
    monkeypatch.setattr(config, "TIMEZONE", "America/New_York")
    # 14:00 UTC is 10:00 in New York (business hours); 03:00 UTC is 23:00 (after hours)
    send(client, api_key, [ev("login_success", BASE, logon_type="2")])
    assert alerts(client) == []
    send(client, api_key, [ev("login_success", BASE.replace(hour=3), logon_type="2")])
    assert "11:00 PM" in alerts(client)[0]["description"]


# --- Offline agents ------------------------------------------------------------


def test_offline_agent_alert_and_auto_resolve(client, api_key, db_session):
    send(client, api_key, [])  # heartbeat
    agent = db_session.query(Agent).one()
    agent.last_seen = utcnow() - timedelta(minutes=30)
    db_session.commit()

    assert len(check_offline_agents(db_session)) == 1
    assert check_offline_agents(db_session) == []  # no duplicate while still open
    [alert] = alerts(client)
    assert alert["rule"] == "agent_offline" and alert["host"] == "PC-01"

    send(client, api_key, [])  # agent comes back
    [alert] = alerts(client)
    assert alert["status"] == "resolved"
    assert "automatically" in alert["resolution_note"]


def test_agents_that_never_reported_are_not_offline(db_session, api_key):
    assert check_offline_agents(db_session) == []


# --- Alert API -------------------------------------------------------------------


def test_alert_detail_includes_events(client, api_key):
    send(client, api_key, failures(5))
    alert_id = alerts(client)[0]["id"]
    detail = client.get(f"/api/alerts/{alert_id}").json()
    assert len(detail["events"]) == 5
    assert all(e["event_type"] == "login_failure" for e in detail["events"])


def test_acknowledge_then_resolve(client, api_key):
    send(client, api_key, failures(5))
    alert_id = alerts(client)[0]["id"]

    ack = client.post(f"/api/alerts/{alert_id}/acknowledge").json()
    assert ack["status"] == "acknowledged" and ack["acknowledged_at"]

    done = client.post(f"/api/alerts/{alert_id}/resolve", json={"note": "Blocked at firewall"}).json()
    assert done["status"] == "resolved" and done["resolution_note"] == "Blocked at firewall"

    assert client.post(f"/api/alerts/{alert_id}/resolve").status_code == 409
    assert client.post(f"/api/alerts/{alert_id}/acknowledge").status_code == 409


def test_resolve_without_note_and_missing_alert(client, api_key):
    send(client, api_key, failures(5))
    alert_id = alerts(client)[0]["id"]
    assert client.post(f"/api/alerts/{alert_id}/resolve").json()["resolution_note"] is None
    assert client.get("/api/alerts/9999").status_code == 404


def test_filters_and_summary(client, api_key):
    send(client, api_key, failures(5) + [
        ev("admin_group_added", BASE, username="x", source_ip=None),
        ev("login_success", BASE.replace(hour=2), logon_type="2"),
    ])
    assert len(alerts(client, severity="high")) == 2
    assert len(alerts(client, rule="off_hours_login")) == 1
    off_hours_id = alerts(client, rule="off_hours_login")[0]["id"]
    client.post(f"/api/alerts/{off_hours_id}/resolve")

    summary = client.get("/api/alerts/summary").json()
    assert summary == {
        "open": 2,
        "acknowledged": 0,
        "resolved": 1,
        "active_by_severity": {"high": 2, "medium": 0, "low": 0},
    }


# --- Email -----------------------------------------------------------------------


def test_emails_high_alerts_only_when_configured(client, api_key, monkeypatch):
    sent = []
    monkeypatch.setattr("app.routers.ingest.send_alert_email", sent.append)

    send(client, api_key, failures(5))
    assert sent == []  # email not configured

    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(config, "ALERT_EMAIL_TO", "it@example.com")
    send(client, api_key, failures(5, source_ip="198.51.100.9")
         + [ev("login_success", BASE.replace(hour=3), logon_type="2")])  # medium: not emailed
    assert [s["severity"] for s in sent] == ["high"]
    assert "password-guessing" in sent[0]["title"]


def test_email_message_contents(monkeypatch):
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            captured["server"] = (host, port)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): captured["tls"] = True
        def login(self, user, password): captured["login"] = user
        def send_message(self, msg): captured["msg"] = msg

    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(config, "SMTP_USER", "bot")
    monkeypatch.setattr(config, "ALERT_EMAIL_TO", "it@example.com")
    alert = Alert(id=7, severity="high", title="T", description="D", recommendation="R",
                  host="PC-01", first_seen=BASE)
    notifications.send_alert_email(notifications.alert_snapshot(alert))

    msg = captured["msg"]
    assert captured["server"] == ("smtp.example.com", 587) and captured["tls"] and captured["login"] == "bot"
    assert msg["Subject"] == "[SentinelView HIGH] T"
    assert msg["To"] == "it@example.com"
    assert "What to do:\nR" in msg.get_content()
