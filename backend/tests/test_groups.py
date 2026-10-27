"""Group membership → conversation sync, and people search."""

from fastapi.testclient import TestClient

from app.main import app


def _register(client, email, username):
    r = client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "display_name": username, "password": "correct-horse-battery-staple"},
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_adding_member_syncs_group_conversation():
    owner = TestClient(app)
    member = TestClient(app)
    _register(owner, "g-owner@example.com", "gowner")
    member_id = _register(member, "g-member@example.com", "gmember")

    group = owner.post("/api/groups", json={"name": "Study Group"}).json()
    group_id = group["id"]

    # Owner adds the member directly.
    r = owner.post(f"/api/groups/{group_id}/members", json={"user_id": member_id, "role": "member"})
    assert r.status_code == 201, r.text

    # The member should now see the group conversation in their list.
    convs = member.get("/api/conversations").json()
    group_convs = [c for c in convs if c["group_id"] == group_id]
    assert len(group_convs) == 1, "member should have the group conversation"

    # And the member can post to it.
    conv_id = group_convs[0]["id"]
    send = member.post(f"/api/conversations/{conv_id}/messages", json={"body": "hello group"})
    assert send.status_code == 201, send.text


def test_join_group_syncs_conversation():
    owner = TestClient(app)
    member = TestClient(app)
    _register(owner, "j-owner@example.com", "jowner")
    member_id = _register(member, "j-member@example.com", "jmember")

    group = owner.post("/api/groups", json={"name": "Join Group"}).json()
    group_id = group["id"]

    # Member joins directly (no invitation).
    r = member.post(f"/api/groups/{group_id}/join")
    assert r.status_code == 200, r.text

    convs = member.get("/api/conversations").json()
    assert any(c["group_id"] == group_id for c in convs)


def test_search_returns_other_users():
    alice = TestClient(app)
    bob = TestClient(app)
    _register(alice, "s-alice@example.com", "salice")
    _register(bob, "s-bob@example.com", "sbob")

    # Alice searches for "sbob" and should see Bob (a user), not herself.
    res = alice.get("/api/knowledge/search", params={"q": "sbob"}).json()
    users = [r for r in res if r["type"] == "user"]
    assert len(users) == 1
    assert users[0]["title"] == "sbob"
