from app.models import Agent


def make_event(record_id="1", event_type="login_failure", **overrides):
    event = {
        "record_id": record_id,
        "event_time": "2026-09-29T14:00:00Z",
        "event_type": event_type,
        "username": "alice",
        "source_ip": "203.0.113.5",
        "logon_type": "3",
        "source_event_id": "4625",
    }
    event.update(overrides)
    return event


def post_batch(client, api_key, events, hostname="PC-01"):
    return client.post(
        "/api/ingest/events",
        json={"hostname": hostname, "os": "Windows 11", "events": events},
        headers={"X-API-Key": api_key},
    )


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_rejects_missing_and_wrong_api_key(client, api_key):
    no_key = client.post("/api/ingest/events", json={"hostname": "PC-01", "events": []})
    assert no_key.status_code == 401
    assert post_batch(client, "sv_wrong", []).status_code == 401


def test_stores_events_and_assigns_severity(client, api_key):
    resp = post_batch(
        client,
        api_key,
        [make_event("1"), make_event("2", "admin_group_added", source_ip=None)],
    )
    assert resp.status_code == 200
    assert resp.json() == {"accepted": 2, "duplicates": 0}

    items = client.get("/api/events").json()["items"]
    severities = {e["event_type"]: e["severity"] for e in items}
    assert severities == {"login_failure": "low", "admin_group_added": "high"}
    assert all(e["host"] == "PC-01" for e in items)


def test_resent_events_are_not_duplicated(client, api_key):
    post_batch(client, api_key, [make_event("1"), make_event("2")])
    resp = post_batch(client, api_key, [make_event("2"), make_event("3"), make_event("3")])
    assert resp.json() == {"accepted": 1, "duplicates": 2}
    assert client.get("/api/events").json()["total"] == 3


def test_empty_batch_updates_heartbeat(client, api_key, db_session):
    post_batch(client, api_key, [], hostname="LAB-PC")
    agent = db_session.query(Agent).one()
    assert agent.last_seen is not None
    assert agent.hostname == "LAB-PC"


def test_invalid_ip_is_stored_as_empty(client, api_key):
    post_batch(client, api_key, [make_event("1", source_ip="-")])
    assert client.get("/api/events").json()["items"][0]["source_ip"] is None


def test_rejects_unknown_event_type(client, api_key):
    assert post_batch(client, api_key, [make_event("1", "made_up")]).status_code == 422


def test_filters_and_pagination(client, api_key):
    post_batch(
        client,
        api_key,
        [
            make_event("1", username="alice", event_time="2026-09-29T10:00:00Z"),
            make_event("2", username="bob", event_time="2026-09-29T11:00:00Z"),
            make_event("3", "login_success", username="bob", event_time="2026-09-29T12:00:00Z"),
        ],
    )
    bob = client.get("/api/events", params={"username": "bob"}).json()
    assert bob["total"] == 2
    assert [e["event_type"] for e in bob["items"]] == ["login_success", "login_failure"]  # newest first

    failures = client.get("/api/events", params={"event_type": "login_failure"}).json()
    assert failures["total"] == 2

    window = client.get(
        "/api/events", params={"start": "2026-09-29T10:30:00", "end": "2026-09-29T11:30:00"}
    ).json()
    assert [e["username"] for e in window["items"]] == ["bob"]

    page = client.get("/api/events", params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 3 and len(page["items"]) == 1
