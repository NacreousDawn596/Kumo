"""ICS <-> CalendarEvent helpers for the CalDAV integration.

Serialization is done by hand (deterministic, UTC ``Z`` timestamps, ``VALUE=DATE``
for all-day events) so we control the exact bytes. Parsing reuses ``vobject``
(the same parser Radicale uses) for robustness against client dialects.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.models import CalendarEvent

_UID_SUFFIX = "@kumo"


def event_uid(event: CalendarEvent) -> str:
    """The stable CalDAV UID for an event."""
    return event.uid or f"{event.id}{_UID_SUFFIX}"


def event_href(event: CalendarEvent) -> str:
    return f"{event_uid(event)}.ics"


def href_to_uid(href: str) -> str:
    return href[:-4] if href.endswith(".ics") else href


def find_event(db, user_id: str, uid: str) -> CalendarEvent | None:
    """Resolve a CalDAV UID to the user's event (app id or client UID)."""
    from sqlalchemy import select

    event = db.execute(
        select(CalendarEvent).where(
            CalendarEvent.organizer_id == user_id,
            CalendarEvent.uid == uid,
        )
    ).scalar_one_or_none()
    if event is None and uid.endswith(_UID_SUFFIX):
        event = db.get(CalendarEvent, uid[: -len(_UID_SUFFIX)])
        if event is not None and event.organizer_id != user_id:
            return None
    return event


def _fold(line: str, limit: int = 75) -> str:
    """RFC 5545 content-line folding."""
    if len(line) <= limit:
        return line
    out: list[str] = []
    while len(line) > limit:
        out.append(line[:limit])
        line = " " + line[limit:]
    out.append(line)
    return "\r\n".join(out)


def _escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
    )


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fmt_dt(dt: datetime) -> str:
    return _as_utc(dt).strftime("%Y%m%dT%H%M%SZ")


def to_ics(event: CalendarEvent) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Kumo//Kumo Calendar//EN",
        "BEGIN:VEVENT",
        f"UID:{event_uid(event)}",
        f"DTSTAMP:{_fmt_dt(event.updated_at or event.created_at)}",
    ]
    if event.all_day:
        lines.append(f"DTSTART;VALUE=DATE:{event.start_at.strftime('%Y%m%d')}")
        if event.end_at:
            lines.append(f"DTEND;VALUE=DATE:{event.end_at.strftime('%Y%m%d')}")
    else:
        lines.append(f"DTSTART:{_fmt_dt(event.start_at)}")
        if event.end_at:
            lines.append(f"DTEND:{_fmt_dt(event.end_at)}")
    lines.append(f"SUMMARY:{_escape_text(event.title)}")
    if event.description:
        lines.append(f"DESCRIPTION:{_escape_text(event.description)}")
    if event.location:
        lines.append(f"LOCATION:{_escape_text(event.location)}")
    if event.recurrence:
        lines.append(f"RRULE:{event.recurrence}")
    lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def _tzid(ve) -> str | None:
    params = getattr(getattr(ve, "dtstart", None), "params", None) or {}
    value = params.get("TZID")
    if isinstance(value, list):
        return value[0] if value else None
    return value if isinstance(value, str) else None


def fields_from_vevent(ve) -> dict:
    """Extract Kumo CalendarEvent fields from a parsed vobject VEVENT."""
    title = str(ve.summary.value) if hasattr(ve, "summary") else "Untitled"
    description = str(ve.description.value) if hasattr(ve, "description") else None
    location = str(ve.location.value) if hasattr(ve, "location") else None
    recurrence = str(ve.rrule.value) if hasattr(ve, "rrule") else None

    start = ve.dtstart.value
    all_day = isinstance(start, date) and not isinstance(start, datetime)
    if all_day:
        start_at = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    else:
        start_at = _as_utc(start)

    end_at: datetime | None = None
    if hasattr(ve, "dtend"):
        end = ve.dtend.value
        if all_day and isinstance(end, date) and not isinstance(end, datetime):
            end_at = datetime(end.year, end.month, end.day, tzinfo=timezone.utc)
        elif isinstance(end, datetime):
            end_at = _as_utc(end)

    return {
        "title": title,
        "description": description,
        "location": location,
        "recurrence": recurrence,
        "start_at": start_at,
        "end_at": end_at,
        "all_day": all_day,
        "timezone": _tzid(ve) or "UTC",
    }
