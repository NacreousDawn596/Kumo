"""Shared authorization helpers (deny-by-default)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    File,
    FileShare,
    Group,
    GroupMember,
    Page,
    PagePermission,
    User,
)

# Permission levels, ascending.
PERMISSIONS = ["view", "download", "comment", "annotate", "collaborate", "edit", "manage"]


def _level(permission: str) -> int:
    return PERMISSIONS.index(permission) if permission in PERMISSIONS else -1


def has_level(permission: str | None, required: str) -> bool:
    if permission is None:
        return False
    return _level(permission) >= _level(required)


def group_role(db: Session, user_id: str, group_id: str) -> str | None:
    row = db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    ).scalar_one_or_none()
    return row.role if row else None


def is_group_member(db: Session, user_id: str, group_id: str) -> bool:
    return group_role(db, user_id, group_id) is not None


def file_permission(db: Session, user: User, file: File) -> str | None:
    """Return the highest permission the user has on a file, or None."""
    if file.owner_id == user.id:
        return "manage"
    if file.group_id and is_group_member(db, user.id, file.group_id):
        return "collaborate"
    # Explicit shares to user or their groups / sessions.
    shares = db.execute(
        select(FileShare).where(FileShare.file_id == file.id)
    ).scalars().all()
    best = None
    for share in shares:
        granted = False
        if share.shared_with_user_id == user.id:
            granted = True
        elif share.shared_with_group_id and is_group_member(db, user.id, share.shared_with_group_id):
            granted = True
        elif share.study_session_id and _in_session(db, user.id, share.study_session_id):
            granted = True
        if granted and (best is None or _level(share.permission) > _level(best)):
            best = share.permission
    return best


def _in_session(db: Session, user_id: str, session_id: str) -> bool:
    from app.models import StudySessionMember

    row = db.execute(
        select(StudySessionMember).where(
            StudySessionMember.session_id == session_id,
            StudySessionMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    return row is not None


def page_permission(db: Session, user: User, page: Page) -> str | None:
    if page.owner_id == user.id:
        return "manage"
    if page.group_id and is_group_member(db, user.id, page.group_id):
        return "edit"
    perm = db.execute(
        select(PagePermission).where(
            PagePermission.page_id == page.id,
            PagePermission.subject_type == "user",
            PagePermission.subject_id == user.id,
        )
    ).scalar_one_or_none()
    if perm:
        return perm.permission
    return None
