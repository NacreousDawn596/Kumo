"""Realtime WebSocket router (mounted as /api/ws)."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from app.realtime.ws import ws_endpoint

router = APIRouter()


@router.websocket("/ws")
async def websocket_route(websocket: WebSocket) -> None:
    await ws_endpoint(websocket)
