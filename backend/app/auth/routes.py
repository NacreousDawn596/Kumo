"""Auth routes: register, login, refresh, logout, SchoolApp boundary."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.provider import ProviderNotConfigured, get_provider
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    SchoolAppAssertionRequest,
)
from app.core.config import settings
from app.core.database import get_db
from app.models import User
from app.security.deps import COOKIE_ACCESS, COOKIE_REFRESH, get_current_user
from app.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        COOKIE_ACCESS,
        access,
        max_age=settings.access_token_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    response.set_cookie(
        COOKIE_REFRESH,
        refresh,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/api/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(COOKIE_ACCESS, path="/")
    response.delete_cookie(COOKIE_REFRESH, path="/api/auth")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        user = service.register_local_user(
            db,
            email=body.email,
            username=body.username,
            display_name=body.display_name,
            password=body.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    access = service.issue_access_token(user)
    refresh = service.create_session(db, user, user_agent=request.headers.get("user-agent"), ip=request.client.host if request.client else None)
    _set_auth_cookies(response, access, refresh)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = service.authenticate_local(db, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access = service.issue_access_token(user)
    refresh = service.create_session(db, user, user_agent=request.headers.get("user-agent"), ip=request.client.host if request.client else None)
    _set_auth_cookies(response, access, refresh)
    return UserOut.model_validate(user)


@router.post("/refresh", response_model=UserOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get(COOKIE_REFRESH)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    try:
        new_refresh, user = service.rotate_session(
            db, refresh_token, user_agent=request.headers.get("user-agent"), ip=request.client.host if request.client else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc
    access = service.issue_access_token(user)
    _set_auth_cookies(response, access, new_refresh)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get(COOKIE_REFRESH)
    if refresh_token:
        service.revoke_session(db, refresh_token)
    _clear_auth_cookies(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.get("/provider")
def provider_info():
    return {"provider": settings.auth_provider, "available": settings.auth_provider in ("local", "schoolapp")}


@router.post("/ws-ticket")
def ws_ticket(user: User = Depends(get_current_user)):
    from app.core.security import sign_access_token

    ticket = sign_access_token({"sub": user.id, "purpose": "ws"}, expires_seconds=30)
    return {"ticket": ticket}


@router.post("/schoolapp/assert", response_model=UserOut)
def schoolapp_assert(body: SchoolAppAssertionRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    from app.auth.provider import InvalidAssertion

    try:
        identity = get_provider("schoolapp").verify_assertion(body.assertion)
    except ProviderNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    except InvalidAssertion as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = service.find_or_create_for_identity(
        db, provider=identity.provider, subject=identity.subject,
        email=identity.email, display_name=identity.display_name,
    )
    # Rotate the CalDAV credential on every login (the plaintext is fetched
    # on demand; only the hash is stored here).
    service.rotate_caldav_password(db, user)
    access = service.issue_access_token(user)
    refresh = service.create_session(db, user, user_agent=request.headers.get("user-agent"), ip=request.client.host if request.client else None)
    _set_auth_cookies(response, access, refresh)
    return UserOut.model_validate(user)
