"""Vault HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import FileComment, User
from app.security.authz import has_level
from app.security.deps import get_current_user
from app.vault import service
from app.vault.schemas import FileCommentIn, FileCommentOut, FileOut, FilePatch, ShareIn
from app.vault.storage import storage

router = APIRouter(prefix="/vault", tags=["vault"])


@router.get("/files", response_model=list[FileOut])
def list_files(
    group_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    files = service.list_files(db, user, group_id=group_id)
    return [service.serialize_file(db, user, f) for f in files]


@router.post("/files", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    group_id: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = await service.store_upload(db, user, file, name=name, description=description, group_id=group_id)
    return service.serialize_file(db, user, record)


@router.get("/files/{file_id}", response_model=FileOut)
def get_file(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = service.require_file(db, user, file_id, "view")
    return service.serialize_file(db, user, record)


@router.patch("/files/{file_id}", response_model=FileOut)
def update_file(file_id: str, body: FilePatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = service.require_file(db, user, file_id, "edit")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return service.serialize_file(db, user, record)


@router.get("/files/{file_id}/content")
def download_file(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = service.require_file(db, user, file_id, "download")
    path = storage.open_path(record.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Content missing")
    return FileResponse(path, media_type=record.mime_type, filename=record.name)


@router.get("/files/{file_id}/preview")
def preview_file(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = service.require_file(db, user, file_id, "view")
    path = storage.open_path(record.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Content missing")
    # Serve inline for previewable types; force attachment otherwise.
    disposition = "inline" if record.previewable else "attachment"
    return FileResponse(path, media_type=record.mime_type, filename=record.name, content_disposition_type=disposition)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = service.require_file(db, user, file_id, "manage")
    storage.delete(record.storage_path)
    user.storage_used_bytes = max(0, user.storage_used_bytes - record.size_bytes)
    db.delete(record)
    db.commit()
    return None


@router.post("/files/{file_id}/shares", status_code=status.HTTP_201_CREATED)
def share_file(file_id: str, body: ShareIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = service.require_file(db, user, file_id, "manage")
    share = service.add_share(db, user, record, target_type=body.target_type, target_id=body.target_id, permission=body.permission)
    return {"id": share.id, "permission": share.permission}


@router.get("/files/{file_id}/comments", response_model=list[FileCommentOut])
def list_comments(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = service.require_file(db, user, file_id, "view")
    from sqlalchemy import select
    comments = db.execute(
        select(FileComment).where(FileComment.file_id == record.id).order_by(FileComment.created_at)
    ).scalars().all()
    return [FileCommentOut.model_validate(c) for c in comments]


@router.post("/files/{file_id}/comments", response_model=FileCommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(file_id: str, body: FileCommentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = service.require_file(db, user, file_id, "comment")
    comment = service.add_comment(db, user, record, body=body.body, page_number=body.page_number, anchor=body.anchor, reply_to_id=body.reply_to_id)
    return FileCommentOut.model_validate(comment)
