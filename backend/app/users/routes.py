"""User profile routes and user search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.security.deps import get_current_user
from app.users.schemas import UserOut, UserPublic, UserUpdate
from app.vault.storage import storage

router = APIRouter(prefix="/users", tags=["users"])

MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_AVATAR_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


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


@router.post("/me/avatar")
def upload_avatar(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=400, detail="Avatar must be a PNG, JPEG, WebP, or GIF")
    data = file.file.read(MAX_AVATAR_BYTES + 1)
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="Avatar too large (2 MB max)")
    storage_id = storage.new_storage_id()
    rel = f"avatars/{storage.relative_path(storage_id)}"
    storage.root.joinpath(rel).parent.mkdir(parents=True, exist_ok=True)
    storage.root.joinpath(rel).write_bytes(data)
    # Remove the previous avatar file.
    if user.avatar_path:
        try:
            storage.root.joinpath(user.avatar_path).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
    user.avatar_path = rel
    db.commit()
    return {"avatar_url": f"/api/users/{user.id}/avatar?v={storage_id}"}


@router.get("/{user_id}/avatar")
def get_avatar(user_id: str, db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None or not target.avatar_path:
        raise HTTPException(status_code=404, detail="No avatar")
    path = storage.root.joinpath(target.avatar_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No avatar")
    return FileResponse(path)


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
