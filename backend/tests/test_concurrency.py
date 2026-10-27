"""Concurrency stress test: ~100 concurrent users with no conflicts."""

import asyncio

import httpx
import pytest

from app.core.security import sign_access_token
from app.main import app


async def _register(client, email, username):
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "display_name": username, "password": "correct-horse-battery-staple"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _bearer(user_id):
    return {"Authorization": f"Bearer {sign_access_token({'sub': user_id, 'username': user_id})}"}


@pytest.mark.asyncio
async def test_hundred_concurrent_users_no_conflicts():
    N = 100
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Owner -> group -> conversation -> whiteboard.
        owner_id = await _register(client, "con-owner@example.com", "conowner")
        owner_headers = await _bearer(owner_id)
        g = (await client.post("/api/groups", json={"name": "Concurrency"}, headers=owner_headers)).json()
        group_id = g["id"]
        convs = (await client.get("/api/conversations", headers=owner_headers)).json()
        conv_id = next(c["id"] for c in convs if c["group_id"] == group_id)
        wb = (await client.post("/api/whiteboards", json={"name": "wb", "group_id": group_id}, headers=owner_headers)).json()
        wb_id = wb["id"]

        # Register N users (capturing ids) and join them to the group.
        from app.core.database import SessionLocal
        from app.models import ConversationMember, GroupMember

        ids = []
        db = SessionLocal()
        for i in range(N):
            uid = await _register(client, f"con-{i}@example.com", f"conuser{i}")
            ids.append(uid)
            db.add(GroupMember(group_id=group_id, user_id=uid, role="member"))
            db.add(ConversationMember(conversation_id=conv_id, user_id=uid))
        db.commit()
        db.close()

        # 1) 100 concurrent messages.
        async def send(i):
            r = await client.post(
                f"/api/conversations/{conv_id}/messages",
                json={"body": f"hello {i}"},
                headers=await _bearer(ids[i]),
            )
            return r.status_code

        results = await asyncio.gather(*[send(i) for i in range(N)])
        assert all(s == 201 for s in results), f"message failures: {[s for s in results if s != 201][:5]}"

        msgs = (await client.get(f"/api/conversations/{conv_id}/messages?limit=200", headers=owner_headers)).json()
        assert len(msgs) >= N, f"expected {N} messages, got {len(msgs)}"

        # 2) 100 concurrent whiteboard ops (distinct element ids, server-assigned seq).
        async def draw(i):
            r = await client.post(
                f"/api/whiteboards/{wb_id}/operations",
                json=[{"op_type": "add", "payload": {"id": f"elem-{i}", "type": "rect", "x": i, "y": 0}}],
                headers=await _bearer(ids[i]),
            )
            return r.status_code

        wb_results = await asyncio.gather(*[draw(i) for i in range(N)])
        assert all(s == 201 for s in wb_results), f"whiteboard failures: {[s for s in wb_results if s != 201][:5]}"

        wb_after = (await client.get(f"/api/whiteboards/{wb_id}", headers=owner_headers)).json()
        elem_ids = {e["id"] for e in wb_after["elements"]}
        assert elem_ids == {f"elem-{i}" for i in range(N)}, "whiteboard lost elements"
