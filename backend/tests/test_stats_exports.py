import csv
import io
from datetime import timedelta

from app.models import utcnow


def send(client, api_key, events, hostname="PC-01"):
    resp = client.post("/api/ingest/events", json={"hostname": hostname, "events": events},
                       headers={"X-API-Key": api_key})
    assert resp.status_code == 200, resp.text


def ev(i, event_type, minutes_ago, username="alice", source_ip="203.0.113.5", **extra):
    when = utcnow() - timedelta(minutes=minutes_ago)
    return {"record_id": str(i), "event_time": when.isoformat() + "Z", "event_type": event_type,
            "username": username, "source_ip": source_ip, "logon_type": "2", **extra}


def test_overview_counts(client, api_key):
    send(client, api_key, [
        ev(1, "login_failure", 30, username="alice"),
        ev(2, "login_failure", 31, username="alice"),
        ev(3, "login_failure", 32, username="bob", source_ip="198.51.100.1"),
        ev(4, "login_success", 60),
        ev(5, "login_success", 60 * 30),  # 30 hours ago: outside the 24h window
    ])
    data = client.get("/api/stats/overview", params={"hours": 24}).json()
    assert data["totals"]["events"] == 4
    assert data["totals"]["failed_logins"] == 3
    assert data["totals"]["successful_logins"] == 1
    assert data["top_failed_users"][0] == {"name": "alice", "count": 2}
    assert data["top_failed_ips"][0] == {"name": "203.0.113.5", "count": 2}
    assert data["top_hosts"] == [{"name": "PC-01", "count": 4}]
    assert data["agents"] == {"total": 1, "online": 1, "offline": 0, "never_reported": 0}
    assert data["severity_counts"] == {"low": 3, "info": 1}


def test_overview_timeline_buckets(client, api_key):
    send(client, api_key, [ev(1, "login_failure", 5), ev(2, "login_success", 5), ev(3, "login_success", 60 * 24 * 3)])
    hourly = client.get("/api/stats/overview", params={"hours": 24}).json()["timeline"]
    assert hourly["bucket"] == "hour"
    assert len(hourly["labels"]) in (24, 25)
    assert sum(hourly["series"]["login_failure"]) == 1 and sum(hourly["series"]["login_success"]) == 1
    assert hourly["labels"][0].endswith("Z")  # times are marked as UTC

    daily = client.get("/api/stats/overview", params={"hours": 24 * 7}).json()["timeline"]
    assert daily["bucket"] == "day"
    assert sum(daily["series"]["login_success"]) == 2


def test_overview_counts_active_alerts(client, api_key):
    send(client, api_key, [ev(i, "login_failure", 1) for i in range(5)])
    totals = client.get("/api/stats/overview").json()["totals"]
    assert totals["active_alerts"] == 1 and totals["high_alerts"] == 1 and totals["new_alerts"] == 1


def read_csv(resp):
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    return list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))


def test_events_csv_respects_filters(client, api_key):
    send(client, api_key, [ev(1, "login_failure", 5), ev(2, "login_success", 5), ev(3, "login_failure", 6, username="bob")])
    rows = read_csv(client.get("/api/events/export.csv", params={"event_type": "login_failure"}))
    assert rows[0][:3] == ["time_utc", "computer", "event_type"]
    assert len(rows) == 3
    assert {r[4] for r in rows[1:]} == {"alice", "bob"}


def test_csv_neutralizes_formulas(client, api_key):
    send(client, api_key, [ev(1, "login_failure", 5, username="=HYPERLINK(\"http://evil\")", message="+cmd")])
    rows = read_csv(client.get("/api/events/export.csv"))
    assert rows[1][4].startswith("'=")
    assert rows[1][8] == "'+cmd"


def test_text_search(client, api_key):
    send(client, api_key, [ev(1, "login_failure", 5, username="alice"), ev(2, "login_failure", 5, username="bob")])
    assert client.get("/api/events", params={"q": "ALI"}).json()["total"] == 1
    assert client.get("/api/events", params={"q": "203.0.113"}).json()["total"] == 2


def test_alerts_csv(client, api_key):
    send(client, api_key, [ev(i, "login_failure", 1) for i in range(5)])
    rows = read_csv(client.get("/api/alerts/export.csv", params={"active": True}))
    assert len(rows) == 2 and rows[1][3] == "brute_force"


def test_alert_actions_record_who(client, api_key):
    send(client, api_key, [ev(i, "login_failure", 1) for i in range(5)])
    alert_id = client.get("/api/alerts").json()["items"][0]["id"]
    assert client.post(f"/api/alerts/{alert_id}/acknowledge").json()["acknowledged_by"] == "admin"
    assert client.post(f"/api/alerts/{alert_id}/resolve").json()["resolved_by"] == "admin"
    assert client.get("/api/alerts", params={"active": True}).json()["total"] == 0


def test_pdf_report(client, api_key):
    send(client, api_key, [ev(i, "login_failure", 1, username="ünïcødé-user") for i in range(5)])
    resp = client.get("/api/reports/summary.pdf", params={"hours": 24})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    assert len(resp.content) > 2000


def test_pdf_report_with_no_data(client):
    resp = client.get("/api/reports/summary.pdf")
    assert resp.status_code == 200 and resp.content.startswith(b"%PDF")


def test_security_headers(client):
    headers = client.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in headers["content-security-policy"]


def test_unknown_api_path_is_404_not_the_dashboard(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


def test_daily_buckets_follow_the_business_time_zone(client, api_key, monkeypatch):
    from datetime import datetime, timezone
    from app import config
    monkeypatch.setattr(config, "TIMEZONE", "America/New_York")
    # 9 PM on Oct 14 in New York is 01:00 UTC on Oct 15; it belongs to Oct 14.
    when = datetime(2026, 10, 15, 1, 0, tzinfo=timezone.utc)
    send(client, api_key, [{"record_id": "1", "event_time": when.isoformat(), "event_type": "login_success",
                            "username": "x", "logon_type": "2"}])
    monkeypatch.setattr("app.routers.stats.utcnow", lambda: datetime(2026, 10, 19, 12, 0))
    timeline = client.get("/api/stats/overview", params={"hours": 24 * 7}).json()["timeline"]
    labels = timeline["labels"]
    assert labels[0] == "2026-10-12T04:00:00Z"  # midnight Oct 12 in New York
    assert len(labels) == 8
    oct14 = labels.index("2026-10-14T04:00:00Z")
    assert timeline["series"]["login_success"][oct14] == 1
