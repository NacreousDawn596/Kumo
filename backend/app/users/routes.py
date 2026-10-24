"""User profile routes and user search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.security.deps import get_current_user
from app.users.schemas import UserOut, UserPublic, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.get("/me/storage")
def my_storage(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.vault.service import get_storage_usage

    return get_storage_usage(db, user)


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/search", response_model=list[UserPublic])
def search_users(
    q: str = Query(min_length=1, max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    like = f"%{q.lower()}%"
    rows = db.execute(
        select(User)
        .where(
            User.is_active.is_(True),
            or_(User.username.ilike(like), User.display_name.ilike(like)),
        )
        .limit(20)
    ).scalars().all()
    return [UserPublic.model_validate(r) for r in rows]


@router.get("/{user_id}", response_model=UserPublic)
def get_user(user_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    target = db.get(User, user_id)
    if target is None or not target.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserPublic.model_validate(target)
