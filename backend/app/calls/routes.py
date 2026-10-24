"""Audio call adapter.

Media is exchanged via WebRTC; signaling relays through WebSockets (see the
realtime layer). This module exposes the media-provider adapter boundary.

Group audio requires an SFU (LiveKit recommended). Until a LiveKit server is
deployed, group calls report ``media_provider="none"`` honestly — Kumo never
pretends WebSocket signaling itself carries audio. One-to-one calls use a
peer-to-peer WebRTC path with STUN; TURN is optional and configured via env.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.models import User
from app.security.deps import get_current_user

router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("/config")
def call_config(user: User = Depends(get_current_user)):
    return {
        "media_provider": "peer",  # peer-to-peer WebRTC; group SFU not deployed
        "group_sfu": "none",       # set to "livekit" once LiveKit is configured
        "stun_servers": ["stun:stun.l.google.com:19302"],
        "turn_servers": [],        # populated from TURN_* env vars when set
        "recording_enabled": False,
    }
