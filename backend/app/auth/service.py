"""Auth service: sessions, cookie issuance, registration, login, refresh."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    hash_password,
    hash_token,
    new_token,
    sign_access_token,
    verify_password,
)
from app.models import ExternalIdentity, Session as SessionModel, User, utcnow


def issue_access_token(user: User) -> str:
    return sign_access_token({"sub": user.id, "username": user.username})


def create_session(db: Session, user: User, *, user_agent: str | None, ip: str | None) -> str:
    refresh = new_token()
    session = SessionModel(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh),
        user_agent=user_agent,
        ip_address=ip,
        expires_at=utcnow() + timedelta(seconds=settings.session_ttl_seconds),
    )
    db.add(session)
    db.commit()
    return refresh


def rotate_session(db: Session, refresh_token: str, *, user_agent: str | None, ip: str | None) -> tuple[str, User]:
    token_hash = hash_token(refresh_token)
    session = db.execute(
        select(SessionModel).where(SessionModel.refresh_token_hash == token_hash)
    ).scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        raise ValueError("invalid refresh token")
    if session.expires_at < utcnow():
        raise ValueError("expired refresh token")
    # Rotate: revoke old, issue new.
    session.revoked_at = utcnow()
    db.commit()
    user = db.get(User, session.user_id)
    return create_session(db, user, user_agent=user_agent, ip=ip), user


def revoke_session(db: Session, refresh_token: str) -> None:
    session = db.execute(
        select(SessionModel).where(
            SessionModel.refresh_token_hash == hash_token(refresh_token)
        )
    ).scalar_one_or_none()
    if session and session.revoked_at is None:
        session.revoked_at = utcnow()
        db.commit()


def revoke_all_sessions(db: Session, user: User) -> None:
    now = utcnow()
    for s in db.execute(
        select(SessionModel).where(
            SessionModel.user_id == user.id, SessionModel.revoked_at.is_(None)
        )
    ).scalars():
        s.revoked_at = now
    db.commit()


def register_local_user(
    db: Session,
    *,
    email: str,
    username: str,
    display_name: str,
    password: str,
) -> User:
    existing = db.execute(
        select(User).where((User.email == email) | (User.username == username))
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError("email or username already in use")
    user = User(
        email=email.lower(),
        username=username.lower(),
        display_name=display_name,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_local(db: Session, email: str, password: str) -> User | None:
    user = db.execute(
        select(User).where(User.email == email.lower())
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def find_or_create_for_identity(
    db: Session, *, provider: str, subject: str, email: str | None, display_name: str | None
) -> User:
    identity = db.execute(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == provider, ExternalIdentity.subject == subject
        )
    ).scalar_one_or_none()
    if identity is not None:
        return db.get(User, identity.user_id)

    user: User | None = None
    if email:
        user = db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()

    if user is None:
        base = _username_base(provider, subject, email, display_name)
        username = _unique_username(db, base)
        user = User(
            email=(email or "").lower() or f"{provider}_{subject}@kumo.local",
            username=username,
            display_name=display_name or username,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    db.add(ExternalIdentity(user_id=user.id, provider=provider, subject=subject))
    db.commit()
    return user


def _username_base(provider: str, subject: str, email: str | None, display_name: str | None) -> str:
    """Derive a clean, normalized username for a new identity-linked account."""
    if display_name:
        slug = "".join(c if c.isalnum() else "-" for c in display_name.lower()).strip("-")
        slug = "-".join(part for part in slug.split("-") if part)
        if slug:
            return slug
    if email:
        local = email.split("@", 1)[0].lower()
        local = "".join(c if c.isalnum() else "-" for c in local).strip("-")
        if local:
            return local
    return f"{provider}-{subject.lower()}"


def _unique_username(db: Session, base: str) -> str:
    candidate = base
    n = 1
    while db.execute(select(User).where(User.username == candidate)).scalar_one_or_none():
        candidate = f"{base}{n}"
        n += 1
    return candidate
