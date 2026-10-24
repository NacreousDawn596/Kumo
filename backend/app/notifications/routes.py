"""Notification routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Notification, User, utcnow
from app.security.deps import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


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
