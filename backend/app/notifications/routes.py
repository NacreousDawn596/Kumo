"""Notification routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Notification, User, utcnow
from app.notifications import service
from app.security.deps import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


class PushSubIn(BaseModel):
    endpoint: str
    keys: dict


@router.get("/vapid-public-key")
def vapid_public_key():
    return {"public_key": settings.vapid_public_key, "enabled": bool(settings.vapid_public_key)}


@router.post("/push-subscribe", status_code=status.HTTP_201_CREATED)
def push_subscribe(body: PushSubIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.store_subscription(db, user, body.endpoint, body.keys)
    db.commit()
    return {"ok": True}


@router.post("/push-unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
def push_unsubscribe(body: PushSubIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.remove_subscription(db, user, body.endpoint)
    db.commit()
    return None


@router.get("")
def list_notifications(
    unread_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(100)
    rows = db.execute(stmt).scalars().all()
    out = []
    for n in rows:
        out.append({
            "id": n.id, "type": n.type, "title": n.title, "body": n.body,
            "resource_type": n.resource_type, "resource_id": n.resource_id,
            "read_at": n.read_at, "created_at": n.created_at,
        })
    if unread_only:
        out = [n for n in out if n["read_at"] is None]
    return out


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(notification_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        return None
    n.read_at = utcnow()
    db.commit()
    return None


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = utcnow()
    for n in db.execute(select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))).scalars():
        n.read_at = now
    db.commit()
    return None
