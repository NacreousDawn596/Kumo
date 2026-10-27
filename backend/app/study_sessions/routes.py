"""Study session routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import StudySession, StudySessionMember, StudySessionResource, User, utcnow
from app.security.authz import is_group_member
from app.security.deps import get_current_user

router = APIRouter(prefix="/sessions", tags=["study_sessions"])


class SessionIn(BaseModel):
    name: str
    group_id: str | None = None
    calendar_event_id: str | None = None


class SessionPatch(BaseModel):
    name: str | None = None
    status: str | None = None


def _member(db: Session, session_id: str, user_id: str) -> bool:
    row = db.execute(select(StudySessionMember).where(
        StudySessionMember.session_id == session_id, StudySessionMember.user_id == user_id
    )).scalar_one_or_none()
    return row is not None


def _out(db: Session, s: StudySession) -> dict:
    members = [m.user_id for m in db.execute(select(StudySessionMember).where(StudySessionMember.session_id == s.id)).scalars()]
    resources = [
        {"resource_type": r.resource_type, "resource_id": r.resource_id}
        for r in db.execute(select(StudySessionResource).where(StudySessionResource.session_id == s.id)).scalars()
    ]
    return {
        "id": s.id, "name": s.name, "owner_id": s.owner_id, "group_id": s.group_id,
        "status": s.status, "members": members, "resources": resources,
        "started_at": s.started_at, "ended_at": s.ended_at, "created_at": s.created_at,
    }


@router.get("")
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ids = [m.session_id for m in db.execute(select(StudySessionMember).where(StudySessionMember.user_id == user.id)).scalars()]
    sessions = db.execute(select(StudySession).where(StudySession.id.in_(ids))).scalars().all() if ids else []
    return [_out(db, s) for s in sessions]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_session(body: SessionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.group_id and not is_group_member(db, user.id, body.group_id):
        raise HTTPException(status_code=403, detail="Not a member of this group")
    session = StudySession(name=body.name, owner_id=user.id, group_id=body.group_id)
    db.add(session)
    db.flush()
    db.add(StudySessionMember(session_id=session.id, user_id=user.id))
    db.commit()
    db.refresh(session)
    return _out(db, session)


@router.get("/{session_id}")
def get_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.get(StudySession, session_id)
    if session is None or not _member(db, session_id, user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    return _out(db, session)


@router.patch("/{session_id}")
def update_session(session_id: str, body: SessionPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.get(StudySession, session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(session, key, value)
    db.commit()
    db.refresh(session)
    return _out(db, session)


@router.post("/{session_id}/join")
def join_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.get(StudySession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.group_id and not is_group_member(db, user.id, session.group_id):
        raise HTTPException(status_code=403, detail="Not a member of this group")
    if not _member(db, session_id, user.id):
        db.add(StudySessionMember(session_id=session_id, user_id=user.id))
        db.commit()
    return _out(db, session)


@router.post("/{session_id}/resources", status_code=status.HTTP_201_CREATED)
def add_resource(session_id: str, resource_type: str, resource_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.get(StudySession, session_id)
    if session is None or not _member(db, session_id, user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    db.add(StudySessionResource(session_id=session_id, resource_type=resource_type, resource_id=resource_id, added_by=user.id))
    db.commit()
    return _out(db, session)


@router.post("/{session_id}/invite-link")
def invite_link(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.base import new_id

    session = db.get(StudySession, session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.invite_token:
        session.invite_token = new_id()
        db.commit()
    return {"token": session.invite_token, "url": f"/sessions/join/{session.invite_token}"}


@router.get("/join/{token}")
def session_by_token(token: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.execute(select(StudySession).where(StudySession.invite_token == token)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": session.id,
        "name": session.name,
        "already_member": _member(db, session.id, user.id),
    }


@router.post("/join/{token}")
def join_by_token(token: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.execute(select(StudySession).where(StudySession.invite_token == token)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.group_id and not is_group_member(db, user.id, session.group_id):
        raise HTTPException(status_code=403, detail="Not a member of this group")
    if not _member(db, session.id, user.id):
        db.add(StudySessionMember(session_id=session.id, user_id=user.id))
        db.commit()
    return _out(db, session)
