"""Public file sharing and invite-link tests."""

from fastapi.testclient import TestClient

from app.main import app


def _register(client, email, username):
    r = client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "display_name": username, "password": "correct-horse-battery-staple"},
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_file_public_share_and_revoke():
    owner = TestClient(app)
    anon = TestClient(app)
    _register(owner, "pub-owner@example.com", "pubowner")

    up = owner.post(
        "/api/vault/files",
        files={"file": ("notes.txt", b"hello public", "text/plain")},
        data={"name": "notes.txt"},
    )
    file_id = up.json()["id"]

    # Not public by default.
    assert up.json()["is_public"] is False

    # Make public.
    pub = owner.post(f"/api/vault/files/{file_id}/make-public").json()
    assert pub["public"] is True
    token = pub["token"]

    # Anonymous can read metadata + content via the token.
    assert anon.get(f"/api/public/files/{token}").status_code == 200
    content = anon.get(f"/api/public/files/{token}/content")
    assert content.status_code == 200
    assert content.content == b"hello public"

    # Revoke -> anonymous denied.
    owner.post(f"/api/vault/files/{file_id}/make-private")
    assert anon.get(f"/api/public/files/{token}").status_code == 404


def test_group_invite_link_request_approve():
    owner = TestClient(app)
    member = TestClient(app)
    _register(owner, "link-owner@example.com", "linkowner")
    _register(member, "link-member@example.com", "linkmember")

    group = owner.post("/api/groups", json={"name": "Invite Group"}).json()
    link = owner.post(f"/api/groups/{group['id']}/invite-link").json()

    # Member requests to join via the link.
    r = member.post(f"/api/groups/join/{link['token']}")
    assert r.json().get("requested") is True

    # Owner sees a pending request and approves it.
    invites = owner.get(f"/api/groups/{group['id']}/invitations").json()
    pending = [i for i in invites if i["status"] == "pending"]
    assert len(pending) == 1
    owner.post(f"/api/groups/requests/{pending[0]['id']}/approve")

    # Member is now in the group and its conversation.
    convs = member.get("/api/conversations").json()
    assert any(c["group_id"] == group["id"] for c in convs)
