"""Radicale authentication plugin backed by Kumo's user table.

CalDAV uses HTTP Basic auth, so credentials are checked against the local
password hash (Argon2id). SchoolApp-only accounts without a local password
cannot use Basic auth until they set one.
"""

from __future__ import annotations

from sqlalchemy import select
from radicale import auth

from app.core.database import SessionLocal
from app.core.security import verify_password
from app.models import User


class Auth(auth.BaseAuth):
    def _login(self, login: str, password: str) -> str:
        login = login.strip().lower()
        if not login or not password:
            return ""
        with SessionLocal() as db:
            user = db.execute(
                select(User).where((User.email == login) | (User.username == login))
            ).scalar_one_or_none()
            if user is None or not user.is_active:
                return ""
            if not verify_password(password, user.password_hash):
                return ""
            return user.username
