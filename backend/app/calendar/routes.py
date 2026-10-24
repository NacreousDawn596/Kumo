"""Calendar event routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import CalendarEvent, EventParticipant, User
from app.security.authz import is_group_member
from app.security.deps import get_current_user

router = APIRouter(prefix="/calendar", tags=["calendar"])


class EventIn(BaseModel):
    title: str
    description: str | None = None
    start_at: datetime
    end_at: datetime | None = None
    all_day: bool = False
    timezone: str = "UTC"
    location: str | None = None
    group_id: str | None = None
    participant_ids: list[str] = []


class EventPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool | None = None
    timezone: str | None = None
    location: str | None = None
    study_session_id: str | None = None
    cancelled: bool | None = None


def _out(e: CalendarEvent, my_response: str | None = None) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "description": e.description,
        "start_at": e.start_at,
        "end_at": e.end_at,
        "all_day": e.all_day,
        "timezone": e.timezone,
        "location": e.location,
        "organizer_id": e.organizer_id,
        "group_id": e.group_id,
        "study_session_id": e.study_session_id,
        "cancelled": e.cancelled,
        "my_response": my_response,
        "created_at": e.created_at,
    }


def _visible(db: Session, user: User, e: CalendarEvent) -> str | None:
    if e.organizer_id == user.id:
        return "accepted"
    if e.group_id and is_group_member(db, user.id, e.group_id):
        return "pending"
    row = db.execute(select(EventParticipant).where(EventParticipant.event_id == e.id, EventParticipant.user_id == user.id)).scalar_one_or_none()
    return row.response if row else None


@router.get("")
def list_events(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(CalendarEvent).where(CalendarEvent.cancelled.is_(False))
    if start:
        stmt = stmt.where(CalendarEvent.start_at >= start)
    if end:
        stmt = stmt.where(CalendarEvent.start_at <= end)
    events = db.execute(stmt).scalars().all()
    out = []
    for e in events:
        resp = _visible(db, user, e)
        if resp is not None:
            out.append(_out(e, resp))
    return out


@router.post("", status_code=status.HTTP_201_CREATED)
def create_event(body: EventIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.group_id and not is_group_member(db, user.id, body.group_id):
        raise HTTPException(status_code=403, detail="Not a member of this group")
    event = CalendarEvent(
        title=body.title, description=body.description, start_at=body.start_at,
        end_at=body.end_at, all_day=body.all_day, timezone=body.timezone,
        location=body.location, organizer_id=user.id, group_id=body.group_id,
    )
    db.add(event)
    db.flush()
    for pid in body.participant_ids:
        db.add(EventParticipant(event_id=event.id, user_id=pid, response="pending"))
    db.commit()
    db.refresh(event)
    return _out(event, "accepted")


@router.get("/{event_id}")
def get_event(event_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    resp = _visible(db, user, event)
    if resp is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return _out(event, resp)


@router.patch("/{event_id}")
def update_event(event_id: str, body: EventPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(CalendarEvent, event_id)
    if event is None or event.organizer_id != user.id:
        raise HTTPException(status_code=404, detail="Event not found")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return _out(event)


@router.post("/{event_id}/respond")
def respond(event_id: str, response: str = Query(pattern="^(accepted|declined|tentative)$"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    row = db.execute(select(EventParticipant).where(EventParticipant.event_id == event_id, EventParticipant.user_id == user.id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=403, detail="You are not a participant")
    row.response = response
    db.commit()
    return _out(event, response)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(CalendarEvent, event_id)
    if event is None or event.organizer_id != user.id:
        raise HTTPException(status_code=404, detail="Event not found")
    event.cancelled = True
    db.commit()
    return None
