"""Storage quota, transfer, and unlink tests."""

from fastapi.testclient import TestClient

from app.main import app


def _register(client, email, username, display_name):
    r = client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "display_name": display_name, "password": "correct-horse-battery-staple"},
    )
    assert r.status_code == 201
    return r.json()


def _upload(client, name="doc.pdf", content=b"%PDF-1.4 x"):
    return client.post(
        "/api/vault/files",
        files={"file": (name, content, "application/pdf")},
        data={"name": name},
    )


def test_default_quota_is_500mb():
    c = TestClient(app)
    u = _register(c, "q@example.com", "quota", "Q")
    me = c.get("/api/auth/me").json()
    assert me["id"] == u["id"]
    storage = c.get("/api/users/me/storage").json()
    assert storage["quota_bytes"] == 500 * 1024 * 1024
    assert storage["used_bytes"] == 0


def test_transfer_preserves_file_and_changes_owner():
    alice = TestClient(app)
    bob = TestClient(app)
    _register(alice, "tx-a@example.com", "txa", "A")
    bob_id = _register(bob, "tx-b@example.com", "txb", "B")["id"]

    f = _upload(alice).json()
    file_id = f["id"]
    assert f["owner_id"] != bob_id

    # Alice comments + annotates before transfer.
    alice.post(f"/api/vault/files/{file_id}/comments", json={"body": "important note"})
    alice.post(f"/api/annotations/files/{file_id}", json={"page_number": 1, "tool": "pen", "points": [[0.1, 0.1], [0.2, 0.2]]})

    # Bob cannot transfer (not owner).
    assert bob.post(f"/api/vault/files/{file_id}/transfer", json={"target_user_id": bob_id}).status_code in (403, 404)

    # Alice transfers to Bob.
    resp = alice.post(f"/api/vault/files/{file_id}/transfer", json={"target_user_id": bob_id})
    assert resp.status_code == 200, resp.text
    assert resp.json()["owner_id"] == bob_id

    # Bob now owns it; Alice no longer sees it.
    assert bob.get(f"/api/vault/files/{file_id}").status_code == 200
    assert alice.get(f"/api/vault/files/{file_id}").status_code == 404

    # Everything preserved: comments + annotations still there.
    comments = bob.get(f"/api/vault/files/{file_id}/comments").json()
    assert any(c["body"] == "important note" for c in comments)
    anns = bob.get(f"/api/annotations/files/{file_id}").json()
    assert len(anns) == 1

    # Bob's storage reflects the file.
    bob_storage = bob.get("/api/users/me/storage").json()
    assert bob_storage["owned_bytes"] == f["size_bytes"]


def test_unlink_frees_quota_without_deleting_file():
    alice = TestClient(app)
    bob = TestClient(app)
    _register(alice, "ul-a@example.com", "ula", "A")
    bob_id = _register(bob, "ul-b@example.com", "ulb", "B")["id"]

    f = _upload(alice).json()
    file_id = f["id"]

    # Alice shares directly with Bob.
    alice.post(f"/api/vault/files/{file_id}/shares", json={"target_type": "user", "target_id": bob_id, "permission": "view"})

    # Bob sees it as linked, and it counts toward his storage.
    bob_file = bob.get(f"/api/vault/files/{file_id}").json()
    assert bob_file["is_linked"] is True
    bob_storage = bob.get("/api/users/me/storage").json()
    assert bob_storage["linked_bytes"] == f["size_bytes"]
    assert bob_storage["used_bytes"] == f["size_bytes"]

    # Bob unlinks it.
    assert bob.post(f"/api/vault/files/{file_id}/unlink").status_code == 204

    # Bob's linked storage freed; file still owned by Alice.
    bob_storage = bob.get("/api/users/me/storage").json()
    assert bob_storage["linked_bytes"] == 0
    assert alice.get(f"/api/vault/files/{file_id}").status_code == 200
    assert bob.get(f"/api/vault/files/{file_id}").status_code == 404


def test_transfer_rejected_when_recipient_full():
    alice = TestClient(app)
    bob = TestClient(app)
    _register(alice, "full-a@example.com", "fulla", "A")
    bob_id = _register(bob, "full-b@example.com", "fullb", "B")["id"]

    f = _upload(alice).json()
    file_id = f["id"]

    # Force Bob's quota to zero.
    from app.core.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    user = db.get(User, bob_id)
    user.storage_quota_bytes = 1
    db.commit()
    db.close()

    resp = alice.post(f"/api/vault/files/{file_id}/transfer", json={"target_user_id": bob_id})
    assert resp.status_code == 413
