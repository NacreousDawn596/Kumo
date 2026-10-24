"""Vault service: file records, storage, permissions, comments."""

from __future__ import annotations

import mimetypes

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import File, FileComment, FileShare, FileVersion, User
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

    # Enforce quota.
    if user.storage_used_bytes >= user.storage_quota_bytes:
        raise HTTPException(status_code=413, detail="Storage quota exceeded")

    storage_id = storage.new_storage_id()
    rel = storage.relative_path(storage_id)
    size = await storage.write_stream(rel, _bounded_chunks(upload, settings.max_upload_bytes))

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
    user.storage_used_bytes += size
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
        "permission": file_permission(db, user, file),
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
