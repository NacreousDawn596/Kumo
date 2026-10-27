"""Radicale storage backend backed directly by Kumo's ``calendar_events`` table.

This is the heart of the CalDAV integration: Radicale never writes to its own
filesystem; every collection and item is materialized on demand from the
application database. The database remains the single source of truth, so
changes made in the web app appear to CalDAV clients immediately, and changes
made by CalDAV clients are visible in the web app on the next read.
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

from app.caldav.ical import event_href, event_uid, fields_from_vevent, find_event, href_to_uid, to_ics
from app.core.database import SessionLocal
from app.models import CalendarEvent, User, utcnow

CALENDAR_NAME = "calendar"

# Serialize writes across the storage (single-process Radicale). Reads are
# lock-free; the database itself guards concurrent writers.
_WRITE_LOCK = threading.Lock()

# WebDAV properties that mark the calendar as a calendar (rather than a
# plain address book or collection).
_CALENDAR_PROPS = {
    "tag": "VCALENDAR",
    "D:displayname": "Kumo Calendar",
    "C:calendar-description": "Kumo personal calendar",
    "C:supported-calendar-component-set": "VEVENT",
}


def _http_date(dt: datetime) -> str:
    ts = dt.replace(tzinfo=timezone.utc).timestamp() if dt.tzinfo is None else dt.timestamp()
    return formatdate(ts, usegmt=True)


def _to_ts(dt: datetime) -> float:
    return dt.replace(tzinfo=timezone.utc).timestamp() if dt.tzinfo is None else dt.timestamp()


def _etag(event: CalendarEvent) -> str:
    raw = f"{event.id}:{event.updated_at.isoformat() if event.updated_at else ''}"
    return '"%s"' % hashlib.sha256(raw.encode()).hexdigest()


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

    def _to_item(self, event: CalendarEvent) -> Item:
        start = event.start_at.replace(tzinfo=timezone.utc) if event.start_at.tzinfo is None else event.start_at
        end = event.end_at or start
        end = end.replace(tzinfo=timezone.utc) if end.tzinfo is None else end
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

    def get_meta(self, key: Optional[str] = None):
        if self._is_calendar():
            meta = dict(_CALENDAR_PROPS)
        elif self._is_principal():
            meta = {"tag": "", "D:displayname": self._owner}
        else:
            meta = {"tag": "", "D:displayname": "Root"}
        if key is None:
            return meta
        return meta.get(key)

    def set_meta(self, props) -> None:
        # Calendar-level metadata (color, display name) is not persisted; the
        # database is the source of truth and these are cosmetic.
        return None

    @property
    def last_modified(self) -> str:
        events = self._events()
        if not events:
            return _http_date(utcnow())
        latest = max(e.updated_at or e.created_at for e in events)
        return _http_date(latest)

    def list(self) -> list[str]:
        return [event_href(e) for e in self._events()]

    def _get(self, href: str) -> Optional[CalendarEvent]:
        uid = href_to_uid(href)
        owner_id = self._owner_id()
        if owner_id is None:
            return None
        with SessionLocal() as db:
            return find_event(db, owner_id, uid)

    def get(self, href: str) -> Optional[Item]:
        if not self._is_calendar():
            return None
        event = self._get(href)
        return self._to_item(event) if event else None

    def get_multi(self, hrefs: Iterable[str]):
        for href in hrefs:
            yield (href, self.get(href))

    def get_all(self) -> Iterator[Item]:
        for event in self._events():
            yield self._to_item(event)

    def upload(self, href: str, item: Item) -> tuple[Item, Optional[Item]]:
        ve = item.vobject_item.vevent
        fields = fields_from_vevent(ve)
        uid = item.uid
        owner_id = self._owner_id()
        if owner_id is None:
            raise ValueError("Unknown user")
        with SessionLocal() as db:
            existing = find_event(db, owner_id, uid)
            if existing is not None:
                old = self._to_item(existing)
                existing.title = fields["title"]
                existing.description = fields["description"]
                existing.location = fields["location"]
                existing.recurrence = fields["recurrence"]
                existing.start_at = fields["start_at"]
                existing.end_at = fields["end_at"]
                existing.all_day = fields["all_day"]
                existing.timezone = fields["timezone"]
                existing.uid = uid
                existing.updated_at = utcnow()
                db.commit()
                db.refresh(existing)
                return self._to_item(existing), old

            event = CalendarEvent(
                organizer_id=owner_id,
                uid=uid,
                title=fields["title"],
                description=fields["description"],
                location=fields["location"],
                recurrence=fields["recurrence"],
                start_at=fields["start_at"],
                end_at=fields["end_at"],
                all_day=fields["all_day"],
                timezone=fields["timezone"],
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            return self._to_item(event), None

    def delete(self, href: Optional[str] = None) -> None:
        if href is None:
            # Deleting the whole collection is not supported (the calendar is
            # implicit). Ignore, matching "the calendar always exists".
            return
        uid = href_to_uid(href)
        owner_id = self._owner_id()
        if owner_id is None:
            return
        with SessionLocal() as db:
            event = find_event(db, owner_id, uid)
            if event is not None:
                event.cancelled = True
                event.updated_at = utcnow()
                db.commit()

    def sync(self, old_token: str = "") -> tuple[str, Iterable[str]]:
        # Token encodes the latest modification timestamp (microseconds).
        old = int(old_token) if old_token else 0
        owner_id = self._owner_id()
        if owner_id is None:
            return "0", []
        with SessionLocal() as db:
            events = db.execute(
                select(CalendarEvent).where(CalendarEvent.organizer_id == owner_id)
            ).scalars().all()
        latest = 0
        changed: list[str] = []
        for e in events:
            ts = int(_to_ts(e.updated_at or e.created_at) * 1_000_000)
            latest = max(latest, ts)
            if ts >= old:
                # Include cancelled items too; get_multi() returns None for
                # them so clients learn they were deleted.
                changed.append(event_href(e))
        return str(latest), changed


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
            # A direct item href: /{user}/calendar/{href}
            href = "/".join(segments[2:])
            item = calendar.get(href)
            if item is not None:
                yield item

    def move(self, item, to_collection, to_href) -> None:
        raise NotImplementedError("Moving events across collections is not supported")

    def create_collection(self, href, items=None, props=None):
        # Collections are virtual (derived from the user). Nothing to persist;
        # return the collection so Radicale sees it as created.
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
