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


def generate_caldav_password() -> str:
    """A random, unguessable credential for CalDAV Basic auth.

    SchoolApp users never type a password manually; this 32-character token is
    what their external calendar client uses. It is one-way hashed before
    storage and rotated on every login.
    """
    return secrets.token_urlsafe(24)


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


def sign_hmac_token(payload: dict, secret: str, expires_seconds: int) -> str:
    """Sign a JSON payload with HMAC-SHA256, embedding the expiry inside.

    Used for the SchoolApp Worker -> backend assertion. Compact format:
    ``base64url(payload).base64url(hmac)``.
    """
    body = {"exp": int(time.time()) + expires_seconds, **payload}
    payload_b64 = _b64url_encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64url_encode(signature)}"


def verify_hmac_token(token: str, secret: str) -> dict:
    """Verify an HMAC-signed token and return its payload (or raise)."""
    try:
        payload_b64, sig_b64 = token.split(".")
    except (ValueError, AttributeError):
        raise ValueError("malformed token")
    expected = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_decode(sig_b64), expected):
        raise ValueError("bad signature")
    body = json.loads(_b64url_decode(payload_b64))
    if int(body.get("exp", 0)) < int(time.time()):
        raise ValueError("token expired")
    return body
