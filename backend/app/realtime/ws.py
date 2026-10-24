"""WebSocket endpoint wiring."""

from __future__ import annotations

import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from app.core.database import SessionLocal
from app.realtime import authz
from app.realtime.manager import authenticate_ws, envelope, manager

logger = logging.getLogger("kumo.ws")


async def ws_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    user_id = authenticate_ws(token)
    if user_id is None:
        # Accept then close so the handshake completes cleanly.
        await websocket.accept()
        await websocket.close(code=4401)
        return

    await manager.connect(websocket, user_id)
    subscriptions: set[str] = set()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            mtype = msg.get("type")

            if mtype == "subscribe":
                for room in msg.get("rooms", []):
                    if len(room) > 128 or ":" not in room:
                        continue
                    db = SessionLocal()
                    try:
                        ok = authz.can_join_room(db, user_id, room)
                    finally:
                        db.close()
                    if ok:
                        manager.subscribe(websocket, user_id, room)
                        subscriptions.add(room)
                        await manager.send_to(websocket, envelope("subscribed", room, user_id, {"peers": manager.peers(room)}))

            elif mtype == "unsubscribe":
                for room in msg.get("rooms", []):
                    manager.unsubscribe(websocket, user_id, room)
                    subscriptions.discard(room)

            elif mtype == "event":
                room = msg.get("room")
                if room not in subscriptions:
                    continue
                event_type = msg.get("event", {}).get("type", "message")
                data = msg.get("event", {}).get("data", {})
                # Enforce payload size.
                payload = json.dumps(data, default=str)
                if len(payload) > 64 * 1024:
                    continue
                # Re-verify membership on each broadcast (authorization changes
                # are re-checked, revoking access to live relays).
                db = SessionLocal()
                try:
                    ok = authz.can_join_room(db, user_id, room)
                finally:
                    db.close()
                if not ok:
                    continue
                await manager.broadcast(
                    room,
                    envelope(event_type, room, user_id, data),
                    exclude=user_id,
                )

            elif mtype == "ping":
                await manager.send_to(websocket, {"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
