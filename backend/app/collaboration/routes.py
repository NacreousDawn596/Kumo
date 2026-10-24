"""Collaborative PDF annotation routes (separate persistent layer)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import DocumentAnnotation, User
from app.security.authz import file_permission, has_level
from app.security.deps import get_current_user
from app.vault.service import require_file

router = APIRouter(prefix="/annotations", tags=["annotations"])


class AnnotationIn(BaseModel):
    page_number: int
    tool: str
    color: str | None = None
    stroke_width: int | None = None
    points: list
    text: str | None = None
    session_id: str | None = None


def _out(a: DocumentAnnotation) -> dict:
    points = []
    if a.points_json:
        try:
            points = json.loads(a.points_json)
        except (ValueError, TypeError):
            points = []
    return {
        "id": a.id, "file_id": a.file_id, "author_id": a.author_id,
        "page_number": a.page_number, "tool": a.tool, "color": a.color,
        "stroke_width": a.stroke_width, "points": points, "text": a.text,
        "deleted": a.deleted, "session_id": a.session_id,
        "created_at": a.created_at,
    }


def _require_annotate(db: Session, user: User, file_id: str):
    file = require_file(db, user, file_id, "view")
    perm = file_permission(db, user, file)
    if perm is None or not has_level(perm, "annotate"):
        # Owner always annotates.
        if file.owner_id != user.id:
            raise HTTPException(status_code=403, detail="You cannot annotate this file")
    return file


@router.get("/files/{file_id}")
def list_annotations(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_file(db, user, file_id, "view")
    annotations = db.execute(
        select(DocumentAnnotation).where(DocumentAnnotation.file_id == file_id, DocumentAnnotation.deleted.is_(False)).order_by(DocumentAnnotation.created_at)
    ).scalars().all()
    return [_out(a) for a in annotations]


@router.post("/files/{file_id}", status_code=status.HTTP_201_CREATED)
def create_annotation(file_id: str, body: AnnotationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_annotate(db, user, file_id)
    annotation = DocumentAnnotation(
        file_id=file_id, author_id=user.id, page_number=body.page_number, tool=body.tool,
        color=body.color, stroke_width=body.stroke_width,
        points_json=json.dumps(body.points), text=body.text, session_id=body.session_id,
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return _out(annotation)


@router.patch("/{annotation_id}")
def update_annotation(annotation_id: str, body: AnnotationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    annotation = db.get(DocumentAnnotation, annotation_id)
    if annotation is None or annotation.author_id != user.id:
        raise HTTPException(status_code=404, detail="Annotation not found")
    annotation.page_number = body.page_number
    annotation.tool = body.tool
    annotation.color = body.color
    annotation.stroke_width = body.stroke_width
    annotation.points_json = json.dumps(body.points)
    annotation.text = body.text
    db.commit()
    db.refresh(annotation)
    return _out(annotation)


@router.delete("/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annotation(annotation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    annotation = db.get(DocumentAnnotation, annotation_id)
    if annotation is None or annotation.author_id != user.id:
        raise HTTPException(status_code=404, detail="Annotation not found")
    annotation.deleted = True
    db.commit()
    return None
