"""Whiteboard routes: persistence via operation log + snapshot."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Whiteboard, WhiteboardOperation, User
from app.security.authz import is_group_member
from app.security.deps import get_current_user

router = APIRouter(prefix="/whiteboards", tags=["whiteboards"])

TEMPLATES = ["mathematics", "physics", "mechanics", "circuits", "chemistry", "organic_chemistry", "lab_report", "engineering", "revision", "brainstorming"]


class WhiteboardIn(BaseModel):
    name: str
    group_id: str | None = None
    session_id: str | None = None
    template: str | None = None


def _can_access(db: Session, user: User, wb: Whiteboard) -> bool:
    if wb.owner_id == user.id:
        return True
    if wb.group_id and is_group_member(db, user.id, wb.group_id):
        return True
    return False


def _out(wb: Whiteboard) -> dict:
    snapshot = None
    if wb.snapshot_json:
        try:
            snapshot = json.loads(wb.snapshot_json)
        except (ValueError, TypeError):
            snapshot = None
    return {
        "id": wb.id, "name": wb.name, "owner_id": wb.owner_id,
        "group_id": wb.group_id, "session_id": wb.session_id,
        "template": wb.template, "elements": snapshot or [],
        "created_at": wb.created_at, "updated_at": wb.updated_at,
    }


@router.get("")
def list_whiteboards(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wbs = db.execute(select(Whiteboard).where(Whiteboard.owner_id == user.id)).scalars().all()
    return [_out(w) for w in wbs]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_whiteboard(body: WhiteboardIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.group_id and not is_group_member(db, user.id, body.group_id):
        raise HTTPException(status_code=403, detail="Not a member of this group")
    wb = Whiteboard(name=body.name, owner_id=user.id, group_id=body.group_id, session_id=body.session_id, template=body.template)
    db.add(wb)
    db.commit()
    db.refresh(wb)
    return _out(wb)


@router.get("/{whiteboard_id}")
def get_whiteboard(whiteboard_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wb = db.get(Whiteboard, whiteboard_id)
    if wb is None or not _can_access(db, user, wb):
        raise HTTPException(status_code=404, detail="Whiteboard not found")
    return _out(wb)


class OpIn(BaseModel):
    op_type: str
    payload: dict


@router.post("/{whiteboard_id}/operations", status_code=status.HTTP_201_CREATED)
def append_operations(whiteboard_id: str, ops: list[OpIn], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wb = db.get(Whiteboard, whiteboard_id)
    if wb is None or not _can_access(db, user, wb):
        raise HTTPException(status_code=404, detail="Whiteboard not found")
    for op in ops:
        db.add(WhiteboardOperation(
            whiteboard_id=whiteboard_id, user_id=user.id,
            op_type=op.op_type, payload_json=json.dumps(op.payload),
        ))
    # The sequence is assigned by SQLite (AUTOINCREMENT) — no client-supplied
    # order, so concurrent operations never collide.
    db.flush()
    # Rebuild snapshot deterministically from the full op log.
    elements = _replay(db, whiteboard_id)
    wb.snapshot_json = json.dumps(elements)
    db.commit()
    return {"applied": len(ops)}


def _replay(db: Session, whiteboard_id: str) -> list[dict]:
    ops = db.execute(
        select(WhiteboardOperation).where(WhiteboardOperation.whiteboard_id == whiteboard_id).order_by(WhiteboardOperation.seq)
    ).scalars().all()
    elements: dict[str, dict] = {}
    for op in ops:
        payload = json.loads(op.payload_json)
        elem_id = payload.get("id")
        if op.op_type in ("add", "update"):
            if elem_id:
                if op.op_type == "add":
                    elements[elem_id] = payload
                else:
                    existing = elements.get(elem_id, {})
                    existing.update(payload)
                    elements[elem_id] = existing
        elif op.op_type == "remove" and elem_id:
            elements.pop(elem_id, None)
    return list(elements.values())
