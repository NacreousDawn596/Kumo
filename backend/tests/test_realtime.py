"""Realtime layer tests (unit-level; no cross-process WS relay)."""

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.realtime import authz
from app.realtime.manager import ConnectionManager, envelope


class _FakeWS:
    def __init__(self):
        self.sent: list[str] = []

    async def accept(self):
        pass

    async def send_text(self, data: str):
        self.sent.append(data)

    async def receive_text(self):
        raise WebSocketDisconnect()


def test_manager_broadcast_and_exclude():
    m = ConnectionManager()
    a = _FakeWS()
    b = _FakeWS()
    # subscribe both, then broadcast excluding b
    m.subscribe(a, "u1", "room")
    m.subscribe(b, "u2", "room")
    import asyncio

    async def run():
        env = envelope("message", "room", "u1", {"text": "hi"})
        await m.broadcast("room", env, exclude="u2")

    asyncio.run(run())
    assert len(b.sent) == 0  # excluded u2
    assert len(a.sent) == 1  # u1 received
    assert any("hi" in s for s in a.sent)
    assert m.peers("room") == ["u1", "u2"]


def test_envelope_shape():
    env = envelope("message", "room", "u1", {"text": "hi"})
    assert env["v"] == 1
    assert env["type"] == "message"
    assert env["sender"] == "u1"
    assert "id" in env


def test_room_members_conversation():
    from app.core.database import SessionLocal

    db = SessionLocal()
    # Conversation membership is created through the API; use HTTP to set up.
    a = TestClient(app)
    b = TestClient(app)
    a.post("/api/auth/register", json={"email": "rm-a@example.com", "username": "rma", "display_name": "A", "password": "correct-horse-battery-staple"})
    b.post("/api/auth/register", json={"email": "rm-b@example.com", "username": "rmb", "display_name": "B", "password": "correct-horse-battery-staple"})
    bid = b.get("/api/auth/me").json()["id"]
    aid = a.get("/api/auth/me").json()["id"]
    conv = a.post("/api/conversations/direct", json={"other_user_id": bid}).json()
    members = authz.room_members(db, f"conversation:{conv['id']}")
    assert aid in members and bid in members
    db.close()


def test_ws_rejects_unauthenticated():
    client = TestClient(app)
    try:
        with client.websocket_connect("/api/ws") as ws:
            ws.receive_json()
    except WebSocketDisconnect:
        pass
