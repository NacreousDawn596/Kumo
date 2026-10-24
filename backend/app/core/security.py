"""Cryptographic helpers: password hashing, tokens, signed access tokens.

Uses stdlib + argon2-cffi + cryptography only. No secrets are logged.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def sign_access_token(payload: dict, expires_seconds: int | None = None) -> str:
    ttl = expires_seconds or settings.access_token_ttl_seconds
    exp = int(time.time()) + ttl
    body = {"exp": exp, **payload}
    payload_b64 = _b64url_encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        settings.secret_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(signature)
    return f"{payload_b64}.{sig_b64}.{exp}"


def verify_access_token(token: str) -> dict:
    try:
        payload_b64, sig_b64, exp_raw = token.split(".")
        exp = int(exp_raw)
    except (ValueError, AttributeError):
        raise ValueError("malformed token")
    if exp < int(time.time()):
        raise ValueError("token expired")
    expected = hmac.new(
        settings.secret_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(_b64url_decode(sig_b64), expected):
        raise ValueError("bad signature")
    return json.loads(_b64url_decode(payload_b64))
