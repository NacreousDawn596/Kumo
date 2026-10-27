"""Vault service: file records, storage, permissions, comments."""

from __future__ import annotations

import mimetypes

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    File,
    FileComment,
    FileShare,
    FileVersion,
    Notification,
    User,
)
from app.security.authz import file_permission, has_level, is_group_member
from app.vault.storage import storage

PREVIEWABLE = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
}


def _previewable(mime: str) -> bool:
    return mime in PREVIEWABLE or mime.startswith("text/")


async def store_upload(
    db: Session,
    user: User,
    upload: UploadFile,
    *,
    name: str | None,
    description: str | None,
    group_id: str | None,
) -> File:
    if group_id and not is_group_member(db, user.id, group_id):
        raise HTTPException(status_code=403, detail="Not a member of this group")
    filename = name or upload.filename or "unnamed"
    mime = upload.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    # Enforce quota (owned + linked files count against personal storage).
    usage = get_storage_usage(db, user)
    if usage["used_bytes"] >= user.storage_quota_bytes:
        raise HTTPException(status_code=413, detail="Storage quota exceeded")

    storage_id = storage.new_storage_id()
    rel = storage.relative_path(storage_id)
    size = await storage.write_stream(rel, _bounded_chunks(upload, settings.max_upload_bytes))

    if usage["used_bytes"] + size > user.storage_quota_bytes:
        storage.delete(rel)
        raise HTTPException(status_code=413, detail="Storage quota exceeded")

    file = File(
        owner_id=user.id,
        name=filename,
        description=description,
        mime_type=mime,
        size_bytes=size,
        storage_id=storage_id,
        storage_path=rel,
        group_id=group_id,
        previewable=_previewable(mime),
    )
    db.add(file)
    db.flush()
    db.add(FileVersion(
        file_id=file.id, version=1, storage_id=storage_id, storage_path=rel,
        size_bytes=size, created_by=user.id,
    ))
    db.commit()
    db.refresh(file)
    return file


async def _bounded_chunks(upload: UploadFile, max_bytes: int):
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="File too large")
        yield chunk


def require_file(db: Session, user: User, file_id: str, required: str = "view") -> File:
    file = db.get(File, file_id)
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    perm = file_permission(db, user, file)
    if perm is None or not has_level(perm, required):
        raise HTTPException(status_code=404, detail="File not found")
    return file


def list_files(db: Session, user: User, *, group_id: str | None = None) -> list[File]:
    stmt = select(File)
    if group_id:
        if not is_group_member(db, user.id, group_id):
            raise HTTPException(status_code=403, detail="Not a member")
        stmt = stmt.where(File.group_id == group_id)
    else:
        stmt = stmt.where(File.group_id.is_(None))
    files = db.execute(stmt.order_by(File.updated_at.desc())).scalars().all()
    return [f for f in files if file_permission(db, user, f) is not None]


def serialize_file(db: Session, user: User, file: File) -> dict:
    perm = file_permission(db, user, file)
    return {
        "id": file.id,
        "name": file.name,
        "description": file.description,
        "mime_type": file.mime_type,
        "size_bytes": file.size_bytes,
        "is_folder": file.is_folder,
        "previewable": file.previewable,
        "owner_id": file.owner_id,
        "group_id": file.group_id,
        "created_at": file.created_at,
        "updated_at": file.updated_at,
        "permission": perm,
        "is_linked": file.owner_id != user.id and perm is not None,
        "is_public": file.is_public,
        "public_token": file.public_token,
    }


def add_share(db: Session, user: User, file: File, *, target_type: str, target_id: str, permission: str) -> FileShare:
    if not has_level(file_permission(db, user, file), "manage"):
        raise HTTPException(status_code=403, detail="You cannot manage sharing for this file")
    share = FileShare(file_id=file.id, permission=permission)
    if target_type == "user":
        share.shared_with_user_id = target_id
    elif target_type == "group":
        share.shared_with_group_id = target_id
    elif target_type == "session":
        share.study_session_id = target_id
    else:
        raise HTTPException(status_code=400, detail="Unknown share target")
    db.add(share)
    db.commit()
    db.refresh(share)
    return share


def add_comment(db: Session, user: User, file: File, *, body: str, page_number: int | None, anchor: str | None, reply_to_id: str | None) -> FileComment:
    perm = file_permission(db, user, file)
    if perm is None or not has_level(perm, "comment"):
        raise HTTPException(status_code=403, detail="You cannot comment on this file")
    comment = FileComment(file_id=file.id, author_id=user.id, body=body, page_number=page_number, anchor=anchor, reply_to_id=reply_to_id)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def get_storage_usage(db: Session, user: User) -> dict:
    """Compute personal storage usage.

    Personal storage includes both owned files and files shared directly with
    the user ("linked" files). Group/session shares do not count toward the
    personal quota.
    """
    owned = db.execute(
        select(func.coalesce(func.sum(File.size_bytes), 0)).where(
            File.owner_id == user.id, File.is_folder.is_(False)
        )
    ).scalar_one()
    linked = db.execute(
        select(func.coalesce(func.sum(File.size_bytes), 0))
        .join(FileShare, FileShare.file_id == File.id)
        .where(
            FileShare.shared_with_user_id == user.id,
            File.owner_id != user.id,
            File.is_folder.is_(False),
        )
    ).scalar_one()
    return {
        "quota_bytes": user.storage_quota_bytes,
        "owned_bytes": int(owned),
        "linked_bytes": int(linked),
        "used_bytes": int(owned) + int(linked),
    }


def transfer_file(db: Session, owner: User, file: File, target: User) -> File:
    """Transfer ownership to another student, preserving every record.

    The file row, versions, shares, comments, and annotations all reference
    ``file.id``, which does not change — only ``owner_id`` changes. The source
    document is neither copied nor deleted.
    """
    if file.owner_id != owner.id:
        raise HTTPException(status_code=403, detail="Only the owner can transfer this file")
    if target.id == owner.id:
        raise HTTPException(status_code=400, detail="File is already owned by you")
    usage = get_storage_usage(db, target)
    if usage["used_bytes"] + file.size_bytes > target.storage_quota_bytes:
        raise HTTPException(status_code=413, detail="Recipient does not have enough storage")
    file.owner_id = target.id
    # Drop the recipient's prior share link (they now own it, so it is no longer "linked").
    prior = db.execute(
        select(FileShare).where(
            FileShare.file_id == file.id, FileShare.shared_with_user_id == target.id
        )
    ).scalars().all()
    for share in prior:
        db.delete(share)
    db.add(
        Notification(
            user_id=target.id,
            type="file_transfer",
            title=f"{owner.display_name} transferred a file to you",
            body=file.name,
            resource_type="file",
            resource_id=file.id,
        )
    )
    db.commit()
    db.refresh(file)
    return file


def unlink_file(db: Session, user: User, file: File) -> None:
    """Remove a direct share link for a file the user does not own.

    This frees the linked quota without touching the underlying file, which
    remains with its owner.
    """
    if file.owner_id == user.id:
        raise HTTPException(status_code=400, detail="You own this file; use transfer instead")
    share = db.execute(
        select(FileShare).where(
            FileShare.file_id == file.id, FileShare.shared_with_user_id == user.id
        )
    ).scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="No linked share to remove")
    db.delete(share)
    db.commit()


def make_public(db: Session, file: File) -> str:
    """Turn on public sharing and return the public token."""
    file.is_public = True
    if not file.public_token:
        from app.models.base import new_id

        file.public_token = new_id()
    db.commit()
    return file.public_token


def make_private(db: Session, file: File) -> None:
    file.is_public = False
    db.commit()


def get_public_file(db: Session, token: str) -> File | None:
    file = db.execute(
        select(File).where(File.public_token == token, File.is_public.is_(True))
    ).scalar_one_or_none()
    return file
