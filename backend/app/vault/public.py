"""Public file sharing endpoints (no authentication required).

A file is only reachable here if its owner explicitly made it public. The
public token is an unguessable 128-bit identifier; access is read-only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.vault import service
from app.vault.storage import storage

router = APIRouter(prefix="/public/files", tags=["public"])


@router.get("/{token}")
def public_metadata(token: str, db: Session = Depends(get_db)):
    file = service.get_public_file(db, token)
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "id": file.id,
        "name": file.name,
        "mime_type": file.mime_type,
        "size_bytes": file.size_bytes,
        "previewable": file.previewable,
    }


@router.get("/{token}/content")
def public_content(token: str, db: Session = Depends(get_db)):
    file = service.get_public_file(db, token)
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    path = storage.open_path(file.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Content missing")
    disposition = "inline" if file.previewable else "attachment"
    return FileResponse(
        path,
        media_type=file.mime_type,
        filename=file.name,
        content_disposition_type=disposition,
    )
