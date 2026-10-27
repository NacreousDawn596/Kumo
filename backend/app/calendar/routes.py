"""Calendar event routes."""

from __future__ import annotations

from datetime import datetime

from dateutil.rrule import rrulestr
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
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
    recurrence: str | None = None  # RRULE string, e.g. "FREQ=WEEKLY;BYDAY=MO"


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
    recurrence: str | None = None


def _out(e: CalendarEvent, my_response: str | None = None, start_at: datetime | None = None) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "description": e.description,
        "start_at": start_at or e.start_at,
        "end_at": e.end_at,
        "all_day": e.all_day,
        "timezone": e.timezone,
        "location": e.location,
        "organizer_id": e.organizer_id,
        "group_id": e.group_id,
        "study_session_id": e.study_session_id,
        "recurrence": e.recurrence,
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


def _recurrences(e: CalendarEvent, start: datetime, end: datetime) -> list[datetime]:
    """Expand an RRULE within [start, end]. Returns [] for non-recurring events."""
    if not e.recurrence:
        return []
    try:
        rule = rrulestr(e.recurrence, dtstart=e.start_at)
        return [d for d in rule.between(start, end, inc=True)]
    except (ValueError, TypeError):
        return []


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

    # Include recurring events whose first occurrence predates the window.
    if start:
        recurring = db.execute(
            select(CalendarEvent).where(
                CalendarEvent.cancelled.is_(False),
                CalendarEvent.recurrence.is_not(None),
                CalendarEvent.start_at < start,
            )
        ).scalars().all()
        events = list(events) + [e for e in recurring if e.id not in {x.id for x in events}]

    out = []
    for e in events:
        resp = _visible(db, user, e)
        if resp is None:
            continue
        if e.recurrence and start and end:
            for occ in _recurrences(e, start, end):
                out.append(_out(e, resp, start_at=occ))
        else:
            out.append(_out(e, resp))
    # Sort by start time.
    out.sort(key=lambda x: x["start_at"] if x["start_at"] else datetime.min)
    return out


@router.post("", status_code=status.HTTP_201_CREATED)
def create_event(body: EventIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.group_id and not is_group_member(db, user.id, body.group_id):
        raise HTTPException(status_code=403, detail="Not a member of this group")
    if body.recurrence:
        try:
            rrulestr(body.recurrence, dtstart=body.start_at)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid recurrence rule: {exc}") from exc
    event = CalendarEvent(
        title=body.title, description=body.description, start_at=body.start_at,
        end_at=body.end_at, all_day=body.all_day, timezone=body.timezone,
        location=body.location, organizer_id=user.id, group_id=body.group_id,
        recurrence=body.recurrence,
    )
    db.add(event)
    db.flush()
    for pid in body.participant_ids:
        db.add(EventParticipant(event_id=event.id, user_id=pid, response="pending"))
    db.commit()
    db.refresh(event)
    return _out(event, "accepted")


def _dt_fmt(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.strftime("%Y%m%dT%H%M%S")
    return dt.astimezone().strftime("%Y%m%dT%H%M%SZ")


@router.get("/export.ics")
def export_ics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    events = db.execute(
        select(CalendarEvent).where(
            CalendarEvent.cancelled.is_(False),
            (CalendarEvent.organizer_id == user.id)
            | (CalendarEvent.id.in_(
                select(EventParticipant.event_id).where(EventParticipant.user_id == user.id)
            )),
        )
    ).scalars().all()

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Kumo//Kumo Calendar//EN"]
    for e in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{e.id}@kumo",
            f"DTSTAMP:{_dt_fmt(e.created_at)}",
            f"DTSTART:{_dt_fmt(e.start_at)}",
        ]
        if e.end_at:
            lines.append(f"DTEND:{_dt_fmt(e.end_at)}")
        lines.append(f"SUMMARY:{e.title}")
        if e.description:
            desc = e.description.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,")
            lines.append(f"DESCRIPTION:{desc}")
        if e.location:
            lines.append(f"LOCATION:{e.location}")
        if e.recurrence:
            lines.append(f"RRULE:{e.recurrence}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    ics = "\r\n".join(lines) + "\r\n"
    return Response(content=ics, media_type="text/calendar", headers={"Content-Disposition": 'attachment; filename="kumo.ics"'})


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
