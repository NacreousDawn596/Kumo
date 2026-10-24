"""WebSocket realtime layer: presence, typing, and event relay.

Single backend instance with in-process connection management (documented as
the starting architecture). Events use a versioned envelope; transient events
(typing, cursors) are never persisted.
"""

from __future__ import annotations

import json
import time
import uuid

from fastapi import WebSocket

from app.core.security import verify_access_token


class ConnectionManager:
    def __init__(self) -> None:
        # room -> set of (user_id, websocket)
        self._rooms: dict[str, dict[str, WebSocket]] = {}
        # websocket -> user_id
        self._sockets: dict[WebSocket, str] = {}

    async def connect(self, ws: WebSocket, user_id: str) -> None:
        await ws.accept()
        self._sockets[ws] = user_id

    def disconnect(self, ws: WebSocket) -> None:
        user_id = self._sockets.pop(ws, None)
        if user_id is None:
            return
        for room in self._rooms.values():
            room.pop(user_id, None)

    def subscribe(self, ws: WebSocket, user_id: str, room: str) -> None:
        self._rooms.setdefault(room, {})[user_id] = ws

    def unsubscribe(self, ws: WebSocket, user_id: str, room: str) -> None:
        if room in self._rooms:
            self._rooms[room].pop(user_id, None)

    def peers(self, room: str) -> list[str]:
        return list(self._rooms.get(room, {}).keys())

    async def broadcast(self, room: str, envelope: dict, *, exclude: str | None = None) -> None:
        sockets = list(self._rooms.get(room, {}).items())
        dead: list[str] = []
        for user_id, ws in sockets:
            if user_id == exclude:
                continue
            try:
                await ws.send_text(json.dumps(envelope, default=str))
            except Exception:
                dead.append(user_id)
        for user_id in dead:
            self._rooms.get(room, {}).pop(user_id, None)

    async def send_to(self, ws: WebSocket, envelope: dict) -> None:
        try:
            await ws.send_text(json.dumps(envelope, default=str))
        except Exception:
            pass


manager = ConnectionManager()


def authenticate_ws(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload = verify_access_token(token)
    except ValueError:
        return None
    if payload.get("purpose") != "ws":
        return None
    return payload.get("sub")


def envelope(event_type: str, room: str, sender: str, data: dict) -> dict:
    return {
        "v": 1,
        "id": uuid.uuid4().hex,
        "type": event_type,
        "room": room,
        "sender": sender,
        "data": data,
        "ts": int(time.time()),
    }
