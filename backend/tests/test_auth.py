import pytest

from app import config

from .conftest import PASSWORD, make_user


def login(client, username="admin", password=PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_login_returns_token_that_works(anon_client, admin_user):
    resp = login(anon_client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["username"] == "admin" and body["user"]["role"] == "admin"
    assert "password_hash" not in body["user"]

    me = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["username"] == "admin"
    assert me.json()["last_login"] is not None


def test_username_is_case_insensitive(anon_client, admin_user):
    assert login(anon_client, "ADMIN").status_code == 200


@pytest.mark.parametrize("username,password", [("admin", "wrong-password-1"), ("nobody", PASSWORD)])
def test_wrong_credentials_get_the_same_message(anon_client, admin_user, username, password):
    resp = login(anon_client, username, password)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect username or password"


def test_lockout_after_repeated_failures(anon_client, admin_user):
    for _ in range(config.LOGIN_MAX_FAILURES):
        assert login(anon_client, password="wrong-password-1").status_code == 401
    # Even the right password is refused while locked out.
    resp = login(anon_client)
    assert resp.status_code == 429
    assert "Too many failed sign-ins" in resp.json()["detail"]


def test_disabled_user_cannot_sign_in_and_token_stops_working(client, anon_client, db_session):
    user = make_user(db_session, "temp", "viewer")
    token = login(anon_client, "temp").json()["access_token"]
    client.patch(f"/api/users/{user.id}", json={"is_active": False})

    assert login(anon_client, "temp").status_code == 401
    assert anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("header", [None, "Bearer not-a-token", "Basic abc"])
def test_endpoints_require_sign_in(anon_client, header):
    headers = {"Authorization": header} if header else {}
    for path in ["/api/events", "/api/alerts", "/api/alerts/summary", "/api/agents",
                 "/api/stats/overview", "/api/events/export.csv", "/api/reports/summary.pdf", "/api/users"]:
        assert anon_client.get(path, headers=headers).status_code == 401, path


def test_expired_token_is_rejected(anon_client, admin_user, monkeypatch):
    monkeypatch.setattr(config, "TOKEN_EXPIRE_MINUTES", -1)
    token = login(anon_client).json()["access_token"]
    assert anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_signed_with_other_key_is_rejected(anon_client, admin_user, monkeypatch):
    token = login(anon_client).json()["access_token"]
    monkeypatch.setattr(config, "SECRET_KEY", "a-different-secret-key-entirely")
    assert anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_change_password_signs_out_old_sessions(anon_client, admin_user):
    old = login(anon_client).json()["access_token"]
    resp = anon_client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "New-password-42"},
        headers={"Authorization": f"Bearer {old}"},
    )
    assert resp.status_code == 200
    new = resp.json()["access_token"]

    assert anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401
    assert anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {new}"}).status_code == 200
    assert login(anon_client, password="New-password-42").status_code == 200


def test_change_password_checks_current_and_strength(client):
    wrong = client.post("/api/auth/change-password",
                        json={"current_password": "nope-nope-1", "new_password": "New-password-42"})
    assert wrong.status_code == 400
    weak = client.post("/api/auth/change-password",
                       json={"current_password": PASSWORD, "new_password": "short1"})
    assert weak.status_code == 422


# --- Viewer vs admin -----------------------------------------------------------------


def test_viewer_can_read_everything(viewer_client):
    for path in ["/api/events", "/api/alerts", "/api/agents", "/api/stats/overview",
                 "/api/events/export.csv", "/api/alerts/export.csv", "/api/reports/summary.pdf"]:
        assert viewer_client.get(path).status_code == 200, path


def test_viewer_cannot_change_anything(viewer_client):
    assert viewer_client.post("/api/alerts/1/acknowledge").status_code == 403
    assert viewer_client.post("/api/alerts/1/resolve").status_code == 403
    assert viewer_client.post("/api/agents", json={"name": "PC"}).status_code == 403
    assert viewer_client.post("/api/agents/1/revoke").status_code == 403
    assert viewer_client.get("/api/users").status_code == 403
    assert viewer_client.post("/api/users", json={"username": "x1x", "password": PASSWORD}).status_code == 403
