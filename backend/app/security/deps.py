"""FastAPI dependencies for authentication and authorization."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_access_token
from app.models import User

COOKIE_ACCESS = "kumo_access"
COOKIE_REFRESH = "kumo_refresh"


def _read_access_token(request: Request) -> str | None:
    cookie = request.cookies.get(COOKIE_ACCESS)
    if cookie:
        return cookie
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer ") :].strip()
    return None


def get_optional_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    token = _read_access_token(request)
    if not token:
        return None
    try:
        payload = verify_access_token(token)
    except ValueError:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user
