"""Smoke test for the auth flow and app boot."""

from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_login_me():
    client = TestClient(app)
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "alice@example.com",
            "username": "alice",
            "display_name": "Alice",
            "password": "correct-horse-battery-staple",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["username"] == "alice"

    # me with cookies
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == data["id"]


def test_login_wrong_password():
    client = TestClient(app)
    resp = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_me_unauthenticated():
    client = TestClient(app)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
