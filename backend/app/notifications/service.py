"""Notification creation helper."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Notification, User


def notify(
    db: Session,
    user_id: str,
    *,
    type: str,
    title: str,
    body: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> Notification:
    n = Notification(
        user_id=user_id, type=type, title=title, body=body,
        resource_type=resource_type, resource_id=resource_id,
    )
    db.add(n)
    return n
