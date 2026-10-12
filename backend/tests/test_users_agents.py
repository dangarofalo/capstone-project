from datetime import timedelta

from sqlalchemy import create_engine, inspect, text

from app.database import add_missing_columns
from app.models import Agent, utcnow

from .conftest import PASSWORD


# --- User management --------------------------------------------------------------


def test_admin_creates_lists_and_deletes_users(client):
    resp = client.post("/api/users", json={"username": "carol", "password": "Strong-pass-77", "role": "viewer"})
    assert resp.status_code == 201
    carol_id = resp.json()["id"]
    assert [u["username"] for u in client.get("/api/users").json()] == ["admin", "carol"]

    assert client.delete(f"/api/users/{carol_id}").status_code == 204
    assert [u["username"] for u in client.get("/api/users").json()] == ["admin"]


def test_new_user_can_sign_in(client, anon_client):
    client.post("/api/users", json={"username": "dave", "password": "Strong-pass-77"})
    resp = anon_client.post("/api/auth/login", json={"username": "dave", "password": "Strong-pass-77"})
    assert resp.json()["user"]["role"] == "viewer"  # default role


def test_rejects_duplicate_usernames_and_weak_passwords(client):
    assert client.post("/api/users", json={"username": "Admin", "password": PASSWORD}).status_code == 409
    assert client.post("/api/users", json={"username": "erin", "password": "short"}).status_code == 422
    assert client.post("/api/users", json={"username": "erin", "password": "onlyletterslong"}).status_code == 422
    assert client.post("/api/users", json={"username": "bad name!", "password": PASSWORD}).status_code == 422


def test_change_role_and_reset_password(client, anon_client):
    uid = client.post("/api/users", json={"username": "frank", "password": PASSWORD}).json()["id"]
    assert client.patch(f"/api/users/{uid}", json={"role": "admin"}).json()["role"] == "admin"
    client.patch(f"/api/users/{uid}", json={"password": "Reset-pass-123"})
    ok = anon_client.post("/api/auth/login", json={"username": "frank", "password": "Reset-pass-123"})
    assert ok.status_code == 200


def test_admin_cannot_lock_themselves_out(client, admin_user):
    me = admin_user.id
    assert client.patch(f"/api/users/{me}", json={"role": "viewer"}).status_code == 400
    assert client.patch(f"/api/users/{me}", json={"is_active": False}).status_code == 400
    assert client.delete(f"/api/users/{me}").status_code == 400


def test_other_admins_can_be_demoted_and_disabled(client):
    other = client.post("/api/users", json={"username": "gina", "password": PASSWORD, "role": "admin"}).json()
    assert client.patch(f"/api/users/{other['id']}", json={"role": "viewer"}).json()["role"] == "viewer"
    assert client.patch(f"/api/users/{other['id']}", json={"is_active": False}).json()["is_active"] is False
    roles = {u["username"]: u["role"] for u in client.get("/api/users").json()}
    assert roles == {"admin": "admin", "gina": "viewer"}


def test_missing_user_is_404(client):
    assert client.patch("/api/users/999", json={"role": "viewer"}).status_code == 404
    assert client.delete("/api/users/999").status_code == 404


# --- Computer (agent) management ------------------------------------------------------


def test_add_computer_returns_working_key_once(client):
    resp = client.post("/api/agents", json={"name": "FRONT-DESK"})
    assert resp.status_code == 201
    key = resp.json()["api_key"]
    assert key.startswith("sv_")
    assert resp.json()["agent"]["status"] == "never_reported"

    sent = client.post("/api/ingest/events", json={"hostname": "FRONT-DESK", "events": []},
                       headers={"X-API-Key": key})
    assert sent.status_code == 200
    [agent] = client.get("/api/agents").json()
    assert agent["status"] == "online"
    assert "api_key" not in agent and "api_key_hash" not in agent


def test_duplicate_or_invalid_computer_names(client):
    client.post("/api/agents", json={"name": "PC-1"})
    assert client.post("/api/agents", json={"name": "PC-1"}).status_code == 409
    assert client.post("/api/agents", json={"name": "<script>"}).status_code == 422


def test_offline_status(client, db_session):
    client.post("/api/agents", json={"name": "OLD-PC"})
    agent = db_session.query(Agent).one()
    agent.last_seen = utcnow() - timedelta(hours=2)
    db_session.commit()
    assert client.get("/api/agents").json()[0]["status"] == "offline"


def test_revoke_blocks_key_and_rotate_restores(client):
    created = client.post("/api/agents", json={"name": "LAPTOP"}).json()
    agent_id, old_key = created["agent"]["id"], created["api_key"]

    revoked = client.post(f"/api/agents/{agent_id}/revoke").json()
    assert revoked["status"] == "revoked"
    send = lambda key: client.post("/api/ingest/events", json={"hostname": "L", "events": []},
                                   headers={"X-API-Key": key}).status_code
    assert send(old_key) == 401

    new_key = client.post(f"/api/agents/{agent_id}/rotate-key").json()["api_key"]
    assert new_key != old_key
    assert send(old_key) == 401
    assert send(new_key) == 200


def test_missing_computer_is_404(client):
    assert client.post("/api/agents/999/revoke").status_code == 404


# --- Upgrading an older database -------------------------------------------------------


def test_add_missing_columns_upgrades_stage1_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE agents (id INTEGER PRIMARY KEY, name VARCHAR(100))"))
        conn.execute(text("INSERT INTO agents (name) VALUES ('PC-1')"))
    add_missing_columns(engine)
    add_missing_columns(engine)  # running twice is harmless
    columns = {c["name"] for c in inspect(engine).get_columns("agents")}
    assert "revoked_at" in columns
    with engine.connect() as conn:
        assert conn.execute(text("SELECT name FROM agents")).scalar() == "PC-1"  # data kept
    engine.dispose()
