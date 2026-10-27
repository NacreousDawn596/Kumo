"""Audio call adapter.

1:1 calls use peer-to-peer WebRTC (see the frontend CallBar). Group calls use
LiveKit (an SFU); this module mints LiveKit access tokens and reports the media
provider config. LiveKit is optional — without API keys configured, group-call
token issuance returns 503.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.models import User
from app.security.deps import get_current_user

router = APIRouter(prefix="/calls", tags=["calls"])


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _livekit_configured() -> bool:
    return bool(settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret)


@router.get("/config")
def call_config(user: User = Depends(get_current_user)):
    turn_servers = []
    if settings.turn_uris:
        for uri in [u.strip() for u in settings.turn_uris.split(",") if u.strip()]:
            turn_servers.append({
                "urls": uri,
                "username": settings.turn_username,
                "credential": settings.turn_credential,
            })
    return {
        "media_provider": "peer",
        "group_sfu": "livekit" if _livekit_configured() else "none",
        "stun_servers": ["stun:stun.l.google.com:19302"],
        "turn_servers": turn_servers,
        "recording_enabled": False,
    }


@router.get("/livekit-token")
def livekit_token(room: str, user: User = Depends(get_current_user)):
    if not _livekit_configured():
        raise HTTPException(status_code=503, detail="LiveKit is not configured")
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": settings.livekit_api_key,
        "sub": user.id,
        "name": user.display_name,
        "iat": now,
        "exp": now + 6 * 3600,
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
        },
    }
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(settings.livekit_api_secret.encode(), signing_input, hashlib.sha256).digest()
    return {"token": f"{header_b64}.{payload_b64}.{_b64url(signature)}", "url": settings.livekit_url}
