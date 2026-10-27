"""ICS <-> CalendarEvent helpers for the CalDAV integration.

Serialization is done by hand (deterministic, ``VALUE=DATE`` for all-day events)
so we control the exact bytes. Parsing reuses ``vobject`` (the same parser
Radicale uses) for robustness against client dialects.

Time zones: events are stored in UTC. When an event carries a non-UTC IANA
``TZID``, we emit ``DTSTART;TZID=...`` in local time together with a full
``VTIMEZONE`` definition (from ``icalendar``), and convert back to UTC on parse
(using ``zoneinfo``), so local wall-clock times round-trip across DST.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.models import CalendarEvent, CalendarEventOverride

_UID_SUFFIX = "@kumo"

_OVERRIDE_HREF_RE = re.compile(r"^(.*)-(\d{8}T\d{6}Z)$")


def event_uid(event: CalendarEvent) -> str:
    """The stable CalDAV UID for an event."""
    return event.uid or f"{event.id}{_UID_SUFFIX}"


def event_href(event: CalendarEvent) -> str:
    return f"{event_uid(event)}.ics"


def override_href(uid: str, recurrence_id: datetime) -> str:
    return f"{uid}-{_fmt_utc(_as_utc(recurrence_id))}.ics"


def href_to_uid(href: str) -> str:
    return href[:-4] if href.endswith(".ics") else href


def parse_href(href: str) -> tuple[str, datetime | None]:
    """Split an item href into ``(uid, recurrence_id_or_None)``."""
    name = href_to_uid(href)
    m = _OVERRIDE_HREF_RE.match(name)
    if m:
        return m.group(1), _parse_utc(m.group(2))
    return name, None


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


def _fmt_utc(dt: datetime) -> str:
    return _as_utc(dt).strftime("%Y%m%dT%H%M%SZ")


def _stamp(dt: datetime | None) -> str:
    return _fmt_utc(dt if dt is not None else datetime.now(timezone.utc))


def _parse_utc(value: str) -> datetime:
    dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    return dt.replace(tzinfo=timezone.utc)


def _resolve_tz(tzid: str | None):
    if not tzid or tzid in ("UTC", "Z", "GMT", "Etc/UTC"):
        return timezone.utc
    try:
        return ZoneInfo(tzid)
    except Exception:  # noqa: BLE001 — unknown TZID falls back to UTC
        return timezone.utc


def _uses_tzid(event: CalendarEvent) -> bool:
    return bool(event.timezone) and event.timezone not in ("UTC", "Z", "GMT", "Etc/UTC")


def vtimezone_block(tzid: str) -> str:
    """A full VTIMEZONE definition (with DST rules) for ``tzid``."""
    try:
        from icalendar import Timezone

        return Timezone.from_tzid(tzid).to_ical().decode("utf-8")
    except Exception:  # noqa: BLE001 — unknown/unsupported TZID
        return ""


# --- JSON helpers for EXDATE/RDATE -------------------------------------------------


def load_datetimes(raw: str | None) -> list[datetime]:
    if not raw:
        return []
    try:
        values = json.loads(raw)
    except (ValueError, TypeError):
        return []
    out: list[datetime] = []
    for v in values:
        try:
            dt = datetime.fromisoformat(v)
            out.append(_as_utc(dt))
        except (ValueError, TypeError):
            continue
    return out


def dump_datetimes(values: list[datetime]) -> str | None:
    if not values:
        return None
    return json.dumps([_as_utc(v).isoformat() for v in values])


# --- Serialization -----------------------------------------------------------------


def _dt_lines(event: CalendarEvent, indent_lines: list[str]) -> None:
    if event.all_day:
        indent_lines.append(f"DTSTART;VALUE=DATE:{event.start_at.strftime('%Y%m%d')}")
        if event.end_at:
            indent_lines.append(f"DTEND;VALUE=DATE:{event.end_at.strftime('%Y%m%d')}")
    elif _uses_tzid(event):
        tz = _resolve_tz(event.timezone)
        indent_lines.append(f"DTSTART;TZID={event.timezone}:{_as_utc(event.start_at).astimezone(tz).strftime('%Y%m%dT%H%M%S')}")
        if event.end_at:
            indent_lines.append(f"DTEND;TZID={event.timezone}:{_as_utc(event.end_at).astimezone(tz).strftime('%Y%m%dT%H%M%S')}")
    else:
        indent_lines.append(f"DTSTART:{_fmt_utc(event.start_at)}")
        if event.end_at:
            indent_lines.append(f"DTEND:{_fmt_utc(event.end_at)}")


def _vevent_lines(event: CalendarEvent) -> list[str]:
    lines = ["BEGIN:VEVENT"]
    lines.append(f"UID:{event_uid(event)}")
    lines.append(f"DTSTAMP:{_stamp(event.updated_at or event.created_at)}")
    _dt_lines(event, lines)
    lines.append(f"SUMMARY:{_escape_text(event.title)}")
    if event.description:
        lines.append(f"DESCRIPTION:{_escape_text(event.description)}")
    if event.location:
        lines.append(f"LOCATION:{_escape_text(event.location)}")
    if event.recurrence:
        lines.append(f"RRULE:{event.recurrence}")
    for ex in load_datetimes(event.exdates):
        if event.all_day:
            lines.append(f"EXDATE;VALUE=DATE:{ex.strftime('%Y%m%d')}")
        else:
            lines.append(f"EXDATE:{_fmt_utc(ex)}")
    for rd in load_datetimes(event.rdates):
        if event.all_day:
            lines.append(f"RDATE;VALUE=DATE:{rd.strftime('%Y%m%d')}")
        else:
            lines.append(f"RDATE:{_fmt_utc(rd)}")
    lines.append("END:VEVENT")
    return lines


def _override_vevent_lines(override: CalendarEventOverride, master: CalendarEvent) -> list[str]:
    lines = ["BEGIN:VEVENT"]
    lines.append(f"UID:{event_uid(master)}")
    rid = _as_utc(override.recurrence_id)
    if master.all_day:
        lines.append(f"RECURRENCE-ID;VALUE=DATE:{rid.strftime('%Y%m%d')}")
    else:
        lines.append(f"RECURRENCE-ID:{_fmt_utc(rid)}")
    lines.append(f"DTSTAMP:{_stamp(override.updated_at or override.created_at)}")

    start = override.start_at or master.start_at
    end = override.end_at or master.end_at
    if master.all_day:
        lines.append(f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}")
        if end:
            lines.append(f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}")
    elif _uses_tzid(master):
        tz = _resolve_tz(master.timezone)
        lines.append(f"DTSTART;TZID={master.timezone}:{_as_utc(start).astimezone(tz).strftime('%Y%m%dT%H%M%S')}")
        if end:
            lines.append(f"DTEND;TZID={master.timezone}:{_as_utc(end).astimezone(tz).strftime('%Y%m%dT%H%M%S')}")
    else:
        lines.append(f"DTSTART:{_fmt_utc(start)}")
        if end:
            lines.append(f"DTEND:{_fmt_utc(end)}")

    title = override.title if override.title is not None else master.title
    lines.append(f"SUMMARY:{_escape_text(title)}")
    if override.cancelled:
        lines.append("STATUS:CANCELLED")
    lines.append("END:VEVENT")
    return lines


def _wrap(lines: list[str], tzid: str | None) -> str:
    parts = ["BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Kumo//Kumo Calendar//EN\r\n"]
    if tzid:
        block = vtimezone_block(tzid)
        if block:
            parts.append(block)
    parts.append("\r\n".join(_fold(line) for line in lines) + "\r\n")
    parts.append("END:VCALENDAR\r\n")
    return "".join(parts)


def to_ics(event: CalendarEvent) -> str:
    return _wrap(_vevent_lines(event), event.timezone if _uses_tzid(event) else None)


def override_to_ics(override: CalendarEventOverride, master: CalendarEvent) -> str:
    return _wrap(_override_vevent_lines(override, master), master.timezone if _uses_tzid(master) else None)


def export_collection_ics(events_with_overrides) -> str:
    """Build one VCALENDAR from masters and their overrides (dedup VTIMEZONEs)."""
    parts = ["BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Kumo//Kumo Calendar//EN\r\n"]
    seen_tzids: set[str] = set()
    vevent_lines: list[str] = []
    for event, overrides in events_with_overrides:
        if _uses_tzid(event) and event.timezone not in seen_tzids:
            block = vtimezone_block(event.timezone)
            if block:
                parts.append(block)
            seen_tzids.add(event.timezone)
        vevent_lines.extend(_vevent_lines(event))
        for o in overrides:
            vevent_lines.extend(_override_vevent_lines(o, event))
    parts.append("\r\n".join(_fold(line) for line in vevent_lines) + "\r\n")
    parts.append("END:VCALENDAR\r\n")
    return "".join(parts)


# --- Parsing -----------------------------------------------------------------------


def _tzid(ve) -> str | None:
    params = getattr(getattr(ve, "dtstart", None), "params", None) or {}
    value = params.get("TZID")
    if value is None:
        # vobject moves the original TZID here when it resolves a VTIMEZONE.
        value = params.get("X-VOBJ-ORIGINAL-TZID")
    if isinstance(value, list):
        return value[0] if value else None
    return value if isinstance(value, str) else None


def _dt_to_utc(value, tzid: str | None, all_day: bool) -> datetime:
    if all_day:
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    # If a TZID is present, interpret the wall-clock time with zoneinfo (DST
    # correct); vobject's own tzinfo from a VTIMEZONE is not trusted.
    if tzid:
        naive = value.replace(tzinfo=None) if value.tzinfo is not None else value
        return naive.replace(tzinfo=_resolve_tz(tzid)).astimezone(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _dt_list_to_utc(values, tzid: str | None, all_day: bool) -> list[datetime]:
    out: list[datetime] = []
    for v in _as_list(values):
        if isinstance(v, date):
            out.append(_dt_to_utc(v, tzid, all_day or (isinstance(v, date) and not isinstance(v, datetime))))
    return out


def fields_from_vevent(ve) -> dict:
    """Extract Kumo CalendarEvent fields from a parsed vobject VEVENT."""
    title = str(ve.summary.value) if hasattr(ve, "summary") else "Untitled"
    description = str(ve.description.value) if hasattr(ve, "description") else None
    location = str(ve.location.value) if hasattr(ve, "location") else None
    recurrence = str(ve.rrule.value) if hasattr(ve, "rrule") else None

    start = ve.dtstart.value
    tzid = _tzid(ve)
    all_day = isinstance(start, date) and not isinstance(start, datetime)
    start_at = _dt_to_utc(start, tzid, all_day)

    end_at: datetime | None = None
    if hasattr(ve, "dtend"):
        end_at = _dt_to_utc(ve.dtend.value, tzid, all_day)

    exdates = _dt_list_to_utc(getattr(ve, "exdate", None) and ve.exdate.value, tzid, all_day)
    rdates = _dt_list_to_utc(getattr(ve, "rdate", None) and ve.rdate.value, tzid, all_day)

    recurrence_id: datetime | None = None
    if hasattr(ve, "recurrence_id"):
        rid = ve.recurrence_id.value
        if isinstance(rid, date):
            recurrence_id = _dt_to_utc(rid, tzid, not isinstance(rid, datetime))

    cancelled = False
    if hasattr(ve, "status"):
        cancelled = str(ve.status.value).upper() == "CANCELLED"

    return {
        "title": title,
        "description": description,
        "location": location,
        "recurrence": recurrence,
        "start_at": start_at,
        "end_at": end_at,
        "all_day": all_day,
        "timezone": tzid or "UTC",
        "exdates": exdates,
        "rdates": rdates,
        "recurrence_id": recurrence_id,
        "cancelled": cancelled,
    }
