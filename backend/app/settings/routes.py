"""User settings routes (arbitrary key/value preferences)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User, UserSetting
from app.security.deps import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(UserSetting).where(UserSetting.user_id == user.id)).scalars().all()
    return {r.key: r.value for r in rows}


@router.put("/{key}")
def set_setting(key: str, value: str | None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(UserSetting).where(UserSetting.user_id == user.id, UserSetting.key == key)).scalar_one_or_none()
    if row is None:
        db.add(UserSetting(user_id=user.id, key=key, value=value))
    else:
        row.value = value
    db.commit()
    return {"key": key, "value": value}
