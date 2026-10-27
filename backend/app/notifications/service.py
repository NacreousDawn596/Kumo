"""Notification creation + Web Push delivery."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Notification, PushSubscription, User


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


def _push_enabled() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def send_push(db: Session, user_id: str, title: str, body: str | None) -> None:
    """Deliver a Web Push message to the user's registered subscriptions."""
    if not _push_enabled():
        return
    subs = db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    ).scalars().all()
    if not subs:
        return
    from pywebpush import WebPushException, webpush

    for sub in subs:
        try:
            keys = json.loads(sub.keys_json)
        except (ValueError, TypeError):
            continue
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": keys,
                },
                data=json.dumps({"title": title, "body": body or ""}),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
            )
        except (WebPushException, Exception):  # noqa: BLE001 — best effort
            continue


def store_subscription(db: Session, user: User, endpoint: str, keys: dict) -> None:
    existing = db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    ).scalar_one_or_none()
    if existing is None:
        db.add(PushSubscription(user_id=user.id, endpoint=endpoint, keys_json=json.dumps(keys)))
    else:
        existing.user_id = user.id
        existing.keys_json = json.dumps(keys)


def remove_subscription(db: Session, user: User, endpoint: str) -> None:
    sub = db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == user.id, PushSubscription.endpoint == endpoint
        )
    ).scalar_one_or_none()
    if sub is not None:
        db.delete(sub)
