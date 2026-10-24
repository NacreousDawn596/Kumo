"""Integration tests for the core end-to-end workflow (section 27)."""

from fastapi.testclient import TestClient

from app.main import app


def _register(client, email, username, display_name):
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "display_name": display_name, "password": "correct-horse-battery-staple"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _new_client():
    return TestClient(app)


def test_full_collaboration_workflow():
    # Two users authenticate (separate clients so cookies are isolated).
    alice = _new_client()
    bob = _new_client()
    eve = _new_client()
    _register(alice, "alice@example.com", "alice", "Alice")
    _register(bob, "bob@example.com", "bob", "Bob")
    _register(eve, "eve@example.com", "eve", "Eve")

    # Alice creates a study group.
    g = alice.post("/api/groups", json={"name": "Mechanics Study", "description": "weekly"}).json()
    group_id = g["id"]

    # Alice invites Bob via membership (no accept-flow UI yet; seed membership directly).
    bob_id = bob.get("/api/auth/me").json()["id"]

    from sqlalchemy import select
    from app.core.database import SessionLocal
    from app.models import Conversation, ConversationMember, GroupMember

    db = SessionLocal()
    db.add(GroupMember(group_id=group_id, user_id=bob_id, role="member"))
    conv = db.execute(select(Conversation).where(Conversation.group_id == group_id)).scalar_one()
    db.add(ConversationMember(conversation_id=conv.id, user_id=bob_id))
    db.commit()
    db.close()

    # Both communicate in the group conversation.
    msg = alice.post(f"/api/conversations/{conv.id}/messages", json={"body": "hey bob, ready for the friction chapter?"})
    assert msg.status_code == 201

    # Alice uploads a PDF.
    content = b"%PDF-1.4 fake pdf content for testing"
    up = alice.post(
        "/api/vault/files",
        files={"file": ("chapter5.pdf", content, "application/pdf")},
        data={"name": "chapter5.pdf"},
    )
    assert up.status_code == 201, up.text
    file_id = up.json()["id"]

    # Alice shares it with the group.
    share = alice.post(f"/api/vault/files/{file_id}/shares", json={"target_type": "group", "target_id": group_id, "permission": "annotate"})
    assert share.status_code == 201, share.text

    # Bob can now view the file.
    bob_view = bob.get(f"/api/vault/files/{file_id}")
    assert bob_view.status_code == 200

    # Eve cannot access the file.
    eve_view = eve.get(f"/api/vault/files/{file_id}")
    assert eve_view.status_code == 404

    # Both open a study session.
    session = alice.post("/api/sessions", json={"name": "Chapter 5 revision", "group_id": group_id}).json()
    session_id = session["id"]
    bob.post(f"/api/sessions/{session_id}/join")

    # Both annotate the PDF.
    ann1 = alice.post(f"/api/annotations/files/{file_id}", json={"page_number": 1, "tool": "highlight", "color": "#A66BFF", "points": [[0.1, 0.1], [0.2, 0.2]]})
    assert ann1.status_code == 201
    ann2 = bob.post(f"/api/annotations/files/{file_id}", json={"page_number": 1, "tool": "pen", "points": [[0.3, 0.3]]})
    assert ann2.status_code == 201

    # Both edit a shared whiteboard.
    wb = alice.post("/api/whiteboards", json={"name": "FBD", "group_id": group_id}).json()
    wb_id = wb["id"]
    alice.post(f"/api/whiteboards/{wb_id}/operations", json=[{"seq": 1, "op_type": "add", "payload": {"id": "e1", "type": "rect", "x": 0, "y": 0}}])
    bob.post(f"/api/whiteboards/{wb_id}/operations", json=[{"seq": 2, "op_type": "add", "payload": {"id": "e2", "type": "arrow", "x": 10, "y": 10}}])
    wb_after = alice.get(f"/api/whiteboards/{wb_id}").json()
    assert len(wb_after["elements"]) == 2

    # The group creates a linked note (page) referencing the PDF and whiteboard.
    page = alice.post("/api/pages", json={"title": "Chapter 5 summary", "group_id": group_id}).json()
    page_id = page["id"]
    alice.post(f"/api/pages/{page_id}/links", json={"target_id": page_id})  # self link sanity
    # Add blocks referencing resources.
    alice.put(f"/api/pages/{page_id}/blocks", json=[
        {"id": None, "block_type": "paragraph", "content": "PDF: /vault/files/" + file_id},
        {"id": None, "block_type": "paragraph", "content": "Whiteboard: " + wb_id},
    ])

    # Bob can read the page (group page).
    bob_page = bob.get(f"/api/pages/{page_id}")
    assert bob_page.status_code == 200

    # The group creates a revision task.
    task = alice.post("/api/tasks", json={"title": "Revise friction", "group_id": group_id}).json()
    task_id = task["id"]

    # The task is added to a calendar event that opens the study room.
    event = alice.post("/api/calendar", json={
        "title": "Mechanics revision",
        "start_at": "2026-10-30T10:00:00Z",
        "end_at": "2026-10-30T11:00:00Z",
        "group_id": group_id,
    }).json()
    event_id = event["id"]
    alice.patch(f"/api/calendar/{event_id}", json={"study_session_id": session_id})

    # The saved notes remain available afterward.
    assert alice.get(f"/api/pages/{page_id}").status_code == 200

    # Eve cannot access group resources.
    assert eve.get(f"/api/pages/{page_id}").status_code == 404
    assert eve.get(f"/api/whiteboards/{wb_id}").status_code == 404
    assert eve.get(f"/api/calendar/{event_id}").status_code == 404

    # Removing a participant revokes protected access.
    # (Bob leaves the group)
    bob.post(f"/api/groups/{group_id}/leave")
    # After leaving, Bob no longer has group access to the file.
    bob_view_after = bob.get(f"/api/vault/files/{file_id}")
    assert bob_view_after.status_code == 404


def test_search_respects_permissions():
    alice = _new_client()
    eve = _new_client()
    _register(alice, "searcha@example.com", "searcha", "A")
    _register(eve, "searche@example.com", "searche", "E")
    page = alice.post("/api/pages", json={"title": "secret quantum notes"}).json()
    # Eve searching should not see Alice's private page.
    res = eve.get("/api/knowledge/search", params={"q": "secret quantum"})
    assert res.status_code == 200
    titles = [r["title"] for r in res.json()]
    assert "secret quantum notes" not in titles
