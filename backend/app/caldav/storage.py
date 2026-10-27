"""Radicale storage backend backed directly by Kumo's ``calendar_events`` table.

This is the heart of the CalDAV integration: Radicale never writes to its own
filesystem; every collection and item is materialized on demand from the
application database. The database remains the single source of truth, so
changes made in the web app appear to CalDAV clients immediately, and changes
made by CalDAV clients are visible in the web app on the next read.

Recurring events with per-instance overrides (``RECURRENCE-ID``) are stored as
a master row plus child ``calendar_event_overrides`` rows; each override is
exposed to CalDAV as its own item (same UID, unique href), exactly as RFC 5545
requires.
"""

from __future__ import annotations

import hashlib
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import formatdate
from typing import Iterable, Iterator, Optional

from radicale import pathutils, storage, types
from radicale.item import Item
from sqlalchemy import select

from app.caldav.ical import (
    dump_datetimes,
    event_href,
    event_uid,
    fields_from_vevent,
    find_event,
    href_to_uid,
    override_href,
    override_to_ics,
    parse_href,
    to_ics,
)
from app.core.database import SessionLocal
from app.models import CalendarEvent, CalendarEventOverride, User, UserSetting, utcnow

CALENDAR_NAME = "calendar"

# Serialize writes across the storage (single-process Radicale). Reads are
# lock-free; the database itself guards concurrent writers.
_WRITE_LOCK = threading.Lock()

_DEFAULT_DISPLAYNAME = "Kumo Calendar"

# UserSetting keys for per-user calendar metadata.
_SETTING_DISPLAYNAME = "caldav_displayname"
_SETTING_COLOR = "caldav_color"


def _http_date(dt: datetime) -> str:
    ts = dt.replace(tzinfo=timezone.utc).timestamp() if dt.tzinfo is None else dt.timestamp()
    return formatdate(ts, usegmt=True)


def _to_ts(dt: datetime) -> float:
    return dt.replace(tzinfo=timezone.utc).timestamp() if dt.tzinfo is None else dt.timestamp()


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _etag(obj) -> str:
    raw = f"{obj.id}:{obj.updated_at.isoformat() if obj.updated_at else ''}"
    return '"%s"' % hashlib.sha256(raw.encode()).hexdigest()


def _get_setting(db, user_id: str, key: str) -> str | None:
    row = db.execute(
        select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.key == key)
    ).scalar_one_or_none()
    return row.value if row else None


def _set_setting(db, user_id: str, key: str, value: str | None) -> None:
    row = db.execute(
        select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.key == key)
    ).scalar_one_or_none()
    if value is None:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(UserSetting(user_id=user_id, key=key, value=value))
    else:
        row.value = value


class Collection(storage.BaseCollection):
    def __init__(self, path: str):
        super().__init__()
        self._path = pathutils.strip_path(path)
        self._owner = self._path.split("/", 1)[0] if self._path else ""

    @property
    def path(self) -> str:
        return self._path

    def _is_root(self) -> bool:
        return not self._path

    def _is_principal(self) -> bool:
        return bool(self._path) and "/" not in self._path

    def _is_calendar(self) -> bool:
        return bool(self._path) and self._path.endswith(f"/{CALENDAR_NAME}")

    def _owner_id(self) -> Optional[str]:
        if not self._owner:
            return None
        with SessionLocal() as db:
            user = db.execute(
                select(User).where(User.username == self._owner)
            ).scalar_one_or_none()
            return user.id if user else None

    def _events(self, *, include_cancelled: bool = False) -> list[CalendarEvent]:
        if not self._is_calendar():
            return []
        owner_id = self._owner_id()
        if owner_id is None:
            return []
        with SessionLocal() as db:
            stmt = select(CalendarEvent).where(CalendarEvent.organizer_id == owner_id)
            if not include_cancelled:
                stmt = stmt.where(CalendarEvent.cancelled.is_(False))
            return list(db.execute(stmt.order_by(CalendarEvent.start_at)).scalars().all())

    def _overrides_for(self, db, event_id: str) -> list[CalendarEventOverride]:
        return list(
            db.execute(
                select(CalendarEventOverride)
                .where(CalendarEventOverride.event_id == event_id)
                .order_by(CalendarEventOverride.recurrence_id)
            ).scalars().all()
        )

    def _to_item(self, event: CalendarEvent) -> Item:
        start = _aware(event.start_at)
        end = _aware(event.end_at or event.start_at)
        return Item(
            collection=self,
            href=event_href(event),
            text=to_ics(event),
            etag=_etag(event),
            uid=event_uid(event),
            last_modified=_http_date(event.updated_at or event.created_at),
            component_name="VEVENT",
            time_range=(int(start.timestamp()), int(end.timestamp())),
        )

    def _override_to_item(self, override: CalendarEventOverride, master: CalendarEvent) -> Item:
        start = _aware(override.start_at or master.start_at)
        end = _aware(override.end_at or master.end_at or override.start_at or master.start_at)
        return Item(
            collection=self,
            href=override_href(event_uid(master), override.recurrence_id),
            text=override_to_ics(override, master),
            etag=_etag(override),
            uid=event_uid(master),
            last_modified=_http_date(override.updated_at or override.created_at),
            component_name="VEVENT",
            time_range=(int(start.timestamp()), int(end.timestamp())),
        )

    # --- Metadata (PROPPATCH / PROPFIND) ---------------------------------------

    def get_meta(self, key: Optional[str] = None):
        if self._is_calendar():
            owner_id = self._owner_id()
            displayname = _DEFAULT_DISPLAYNAME
            color = None
            if owner_id:
                with SessionLocal() as db:
                    displayname = _get_setting(db, owner_id, _SETTING_DISPLAYNAME) or _DEFAULT_DISPLAYNAME
                    color = _get_setting(db, owner_id, _SETTING_COLOR)
            meta = {
                "tag": "VCALENDAR",
                "D:displayname": displayname,
                "C:calendar-description": "Kumo personal calendar",
                "C:supported-calendar-component-set": "VEVENT",
            }
            if color:
                meta["ICAL:calendar-color"] = color
        elif self._is_principal():
            meta = {"tag": "", "D:displayname": self._owner}
        else:
            meta = {"tag": "", "D:displayname": "Root"}
        if key is None:
            return meta
        return meta.get(key)

    def set_meta(self, props) -> None:
        if not self._is_calendar():
            return
        owner_id = self._owner_id()
        if owner_id is None:
            return
        with SessionLocal() as db:
            if "D:displayname" in props and props["D:displayname"]:
                _set_setting(db, owner_id, _SETTING_DISPLAYNAME, props["D:displayname"])
            if "ICAL:calendar-color" in props:
                _set_setting(db, owner_id, _SETTING_COLOR, props["ICAL:calendar-color"] or None)
            db.commit()

    @property
    def last_modified(self) -> str:
        events = self._events(include_cancelled=True)
        latest: datetime | None = None
        with SessionLocal() as db:
            for e in events:
                latest = _max_dt(latest, e.updated_at or e.created_at)
                for o in self._overrides_for(db, e.id):
                    latest = _max_dt(latest, o.updated_at or o.created_at)
        if latest is None:
            return _http_date(utcnow())
        return _http_date(latest)

    def list(self) -> list[str]:
        hrefs: list[str] = []
        with SessionLocal() as db:
            for e in self._events():
                hrefs.append(event_href(e))
                for o in self._overrides_for(db, e.id):
                    hrefs.append(override_href(event_uid(e), o.recurrence_id))
        return hrefs

    def _get(self, href: str):
        uid, recurrence_id = parse_href(href)
        owner_id = self._owner_id()
        if owner_id is None:
            return None
        with SessionLocal() as db:
            master = find_event(db, owner_id, uid)
            if master is None or master.cancelled:
                return None
            if recurrence_id is None:
                return master
            override = db.execute(
                select(CalendarEventOverride).where(
                    CalendarEventOverride.event_id == master.id,
                    CalendarEventOverride.recurrence_id == recurrence_id,
                )
            ).scalar_one_or_none()
            return (override, master) if override is not None else None

    def get(self, href: str) -> Optional[Item]:
        if not self._is_calendar():
            return None
        result = self._get(href)
        if result is None:
            return None
        if isinstance(result, tuple):
            return self._override_to_item(result[0], result[1])
        return self._to_item(result)

    def get_multi(self, hrefs: Iterable[str]):
        for href in hrefs:
            yield (href, self.get(href))

    def get_all(self) -> Iterator[Item]:
        with SessionLocal() as db:
            for event in self._events():
                yield self._to_item(event)
                for o in self._overrides_for(db, event.id):
                    yield self._override_to_item(o, event)

    def has_uid(self, uid: str) -> bool:
        # Radicale's default UID-conflict check rejects recurrence overrides
        # (which legitimately share the master's UID). Our storage keys
        # masters by UID and separates overrides by RECURRENCE-ID, so UID
        # conflicts are resolved in ``upload``; always return False here.
        return False

    def upload(self, href: str, item: Item) -> tuple[Item, Optional[Item]]:
        ve = item.vobject_item.vevent
        fields = fields_from_vevent(ve)
        uid = item.uid
        owner_id = self._owner_id()
        if owner_id is None:
            raise ValueError("Unknown user")

        with SessionLocal() as db:
            master = find_event(db, owner_id, uid)

            if fields["recurrence_id"] is not None:
                return self._upload_override(db, owner_id, master, uid, fields)

            if master is not None:
                old = self._to_item(master)
                self._apply_fields(master, fields)
                master.uid = uid
                master.updated_at = utcnow()
                db.commit()
                db.refresh(master)
                return self._to_item(master), old

            event = CalendarEvent(organizer_id=owner_id, uid=uid)
            self._apply_fields(event, fields)
            db.add(event)
            db.commit()
            db.refresh(event)
            return self._to_item(event), None

    def _upload_override(self, db, owner_id, master, uid, fields):
        if master is None:
            master = CalendarEvent(
                organizer_id=owner_id, uid=uid, title=fields["title"] or "Untitled",
                start_at=fields["recurrence_id"], timezone=fields["timezone"],
            )
            db.add(master)
            db.flush()
        override = db.execute(
            select(CalendarEventOverride).where(
                CalendarEventOverride.event_id == master.id,
                CalendarEventOverride.recurrence_id == fields["recurrence_id"],
            )
        ).scalar_one_or_none()
        old = self._override_to_item(override, master) if override is not None else None
        if override is None:
            override = CalendarEventOverride(event_id=master.id, recurrence_id=fields["recurrence_id"])
            db.add(override)
        override.start_at = fields["start_at"]
        override.end_at = fields["end_at"]
        override.title = fields["title"]
        override.cancelled = fields["cancelled"]
        db.commit()
        db.refresh(override)
        db.refresh(master)
        return self._override_to_item(override, master), old

    @staticmethod
    def _apply_fields(event: CalendarEvent, fields: dict) -> None:
        event.title = fields["title"]
        event.description = fields["description"]
        event.location = fields["location"]
        event.recurrence = fields["recurrence"]
        event.start_at = fields["start_at"]
        event.end_at = fields["end_at"]
        event.all_day = fields["all_day"]
        event.timezone = fields["timezone"]
        event.exdates = dump_datetimes(fields["exdates"])
        event.rdates = dump_datetimes(fields["rdates"])

    def delete(self, href: Optional[str] = None) -> None:
        if href is None:
            return
        uid, recurrence_id = parse_href(href)
        owner_id = self._owner_id()
        if owner_id is None:
            return
        with SessionLocal() as db:
            master = find_event(db, owner_id, uid)
            if master is None:
                return
            if recurrence_id is not None:
                override = db.execute(
                    select(CalendarEventOverride).where(
                        CalendarEventOverride.event_id == master.id,
                        CalendarEventOverride.recurrence_id == recurrence_id,
                    )
                ).scalar_one_or_none()
                if override is not None:
                    db.delete(override)
                    db.commit()
                return
            master.cancelled = True
            master.updated_at = utcnow()
            db.commit()

    def sync(self, old_token: str = "") -> tuple[str, Iterable[str]]:
        old = int(old_token) if old_token else 0
        owner_id = self._owner_id()
        if owner_id is None:
            return "0", []
        with SessionLocal() as db:
            masters = db.execute(
                select(CalendarEvent).where(CalendarEvent.organizer_id == owner_id)
            ).scalars().all()
        latest = 0
        changed: list[str] = []
        with SessionLocal() as db:
            for e in masters:
                ts = int(_to_ts(e.updated_at or e.created_at) * 1_000_000)
                latest = max(latest, ts)
                if ts >= old:
                    changed.append(event_href(e))
                for o in self._overrides_for(db, e.id):
                    ots = int(_to_ts(o.updated_at or o.created_at) * 1_000_000)
                    latest = max(latest, ots)
                    if ots >= old:
                        changed.append(override_href(event_uid(e), o.recurrence_id))
        return str(latest), changed


def _max_dt(a: datetime | None, b: datetime) -> datetime:
    if a is None:
        return b
    return a if a >= b else b


class Storage(storage.BaseStorage):
    _collection_class = Collection

    def _collection(self, path: str) -> Collection:
        return Collection(path)

    def discover(
        self,
        path: str,
        depth: str = "0",
        child_context_manager=None,
        user_groups: set = set(),
    ) -> Iterator[types.CollectionOrItem]:
        sane = pathutils.strip_path(path)
        segments = sane.split("/") if sane else []

        if not segments:
            yield self._collection(path)
            return

        user = segments[0]
        if len(segments) == 1:
            yield self._collection(path)
            if depth != "0":
                yield self._collection(f"/{user}/{CALENDAR_NAME}")
            return

        if segments[1] == CALENDAR_NAME:
            calendar = self._collection(f"/{user}/{CALENDAR_NAME}")
            if len(segments) == 2:
                yield calendar
                if depth != "0":
                    for item in calendar.get_all():
                        yield item
                return
            href = "/".join(segments[2:])
            item = calendar.get(href)
            if item is not None:
                yield item

    def move(self, item, to_collection, to_href) -> None:
        raise NotImplementedError("Moving events across collections is not supported")

    def create_collection(self, href, items=None, props=None):
        return self._collection(href), {}, []

    @contextmanager
    def acquire_lock(self, mode: str, user: str = "", *args, **kwargs):
        if mode == "w":
            with _WRITE_LOCK:
                yield
        else:
            yield

    def verify(self) -> bool:
        return True
