"""Page block editing + optimistic concurrency tests."""

from fastapi.testclient import TestClient

from app.main import app


def _register(client, email, username):
    r = client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "display_name": username, "password": "correct-horse-battery-staple"},
    )
    assert r.status_code == 201
    return r.json()


def _blocks(page_id, content="hello"):
    return [{"block_type": "paragraph", "content": content}]


def test_block_edit_bumps_version():
    c = TestClient(app)
    _register(c, "pv-a@example.com", "pva")
    page = c.post("/api/pages", json={"title": "V"}).json()
    assert page["version"] == 0

    r = c.put(f"/api/pages/{page['id']}/blocks", json=_blocks(page["id"]))
    assert r.status_code == 200

    updated = c.get(f"/api/pages/{page['id']}").json()
    assert updated["version"] == 1


def test_stale_version_returns_409():
    c = TestClient(app)
    _register(c, "pv-b@example.com", "pvb")
    page = c.post("/api/pages", json={"title": "W"}).json()
    pid = page["id"]

    # First edit succeeds.
    assert c.put(f"/api/pages/{pid}/blocks", json=_blocks(pid)).status_code == 200

    # Second edit with the OLD version (0) must conflict.
    stale = c.put(
        f"/api/pages/{pid}/blocks?expected_version=0",
        json=_blocks(pid, content="changed"),
    )
    assert stale.status_code == 409

    # Editing with the current version (1) succeeds.
    ok = c.put(
        f"/api/pages/{pid}/blocks?expected_version=1",
        json=_blocks(pid, content="changed"),
    )
    assert ok.status_code == 200
