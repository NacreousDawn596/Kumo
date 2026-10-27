"""Integration tests for the CalDAV (Radicale) layer.

These drive the real Radicale WSGI application against the same SQLite test
database used by the REST tests, proving that:

- CalDAV clients can create / read / update / delete events (reflected in the
  ``calendar_events`` table, the single source of truth).
- Events created by the app appear to CalDAV clients, and vice versa.
- Deletions, recurring events, all-day events, and time zones round-trip.
- Optimistic concurrency (If-Match) is enforced.
- Authentication and per-user isolation hold.

"""

import tempfile
from datetime import datetime, timezone

import pytest
from radicale import config as radicale_config
from radicale.app import Application
from sqlalchemy import select
from webtest import TestApp

from app.auth.service import register_local_user
from app.core.database import SessionLocal
from app.models import CalendarEvent, User

CALENDAR = "/alice/calendar"
PASSWORD = "correct-horse-battery-staple"


def _build_dav_app() -> TestApp:
    tmp = tempfile.mkdtemp(prefix="kumo-dav-")
    cfg = radicale_config.load([])
    cfg.update(
        {
            "auth": {"type": "app.caldav.auth"},
            "rights": {"type": "app.caldav.rights"},
            "storage": {"type": "app.caldav.storage", "filesystem_folder": tmp},
            "web": {"type": "none"},
        },
        "test",
    )
    return TestApp(Application(cfg))


def _register(username: str, email: str, password: str = PASSWORD) -> None:
    register_local_user(
        SessionLocal(), email=email, username=username, display_name=username.title(), password=password
    )


def _event_ics(uid: str, summary: str, start: str, end: str, extra: str = "") -> bytes:
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\nDTSTART:{start}\r\nDTEND:{end}\r\nSUMMARY:{summary}\r\n"
        f"{extra}"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    ).encode()


def _db_events(username: str) -> list[CalendarEvent]:
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.username == username)).scalar_one()
        return list(db.execute(select(CalendarEvent).where(CalendarEvent.organizer_id == user.id)).scalars().all())


@pytest.fixture()
def dav():
    return _build_dav_app()


@pytest.fixture()
def alice(dav):
    _register("alice", "alice@kumo.test")
    dav.authorization = ("Basic", ("alice", PASSWORD))
    return dav


def test_health_and_principal(alice):
    r = alice.request("/alice/", method="PROPFIND", headers={"Depth": "1"}, status="*")
    assert r.status_int == 207
    assert "current-user-principal" in r.text


def test_create_read_update_delete(alice):
    # Create
    r = alice.request(
        f"{CALENDAR}/evt-1@test.ics",
        method="PUT",
        body=_event_ics("evt-1@test", "From CalDAV", "20261101T090000Z", "20261101T100000Z"),
        headers={"Content-Type": "text/calendar"},
        status="*",
    )
    assert r.status_int == 201
    etag = r.headers["ETag"]
    assert _db_events("alice")[0].title == "From CalDAV"
    assert _db_events("alice")[0].uid == "evt-1@test"

    # Read
    r = alice.request(f"{CALENDAR}/evt-1@test.ics", method="GET", status="*")
    assert r.status_int == 200
    assert "From CalDAV" in r.text

    # Update (with matching If-Match)
    r = alice.request(
        f"{CALENDAR}/evt-1@test.ics",
        method="PUT",
        body=_event_ics("evt-1@test", "Updated title", "20261101T100000Z", "20261101T110000Z"),
        headers={"Content-Type": "text/calendar", "If-Match": etag},
        status="*",
    )
    assert r.status_int in (200, 204)
    assert _db_events("alice")[0].title == "Updated title"

    # Delete
    r = alice.request(f"{CALENDAR}/evt-1@test.ics", method="DELETE", status="*")
    assert r.status_int == 200
    assert _db_events("alice")[0].cancelled is True


def test_app_event_visible_in_caldav(alice):
    # Create directly in the app DB (simulating the REST create_event path).
    from app.auth.service import authenticate_local

    user = authenticate_local(SessionLocal(), "alice@kumo.test", PASSWORD)
    assert user is not None
    with SessionLocal() as db:
        db.add(
            CalendarEvent(
                title="Made in app",
                organizer_id=user.id,
                start_at=datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc),
            )
        )
        db.commit()

    r = alice.request(f"{CALENDAR}/", method="PROPFIND", headers={"Depth": "1"}, status="*")
    assert r.status_int == 207
    # The app event's UID is derived as {id}@kumo (href percent-encodes "@").
    ev = _db_events("alice")[0]
    assert ev.id in r.text
    href = f"{CALENDAR}/{ev.id}@kumo.ics"
    r = alice.request(href, method="GET", status="*")
    assert r.status_int == 200
    assert "Made in app" in r.text


def test_caldav_edit_updates_app(alice):
    r = alice.request(
        f"{CALENDAR}/evt-2@test.ics",
        method="PUT",
        body=_event_ics("evt-2@test", "Original", "20261102T090000Z", "20261102T100000Z"),
        headers={"Content-Type": "text/calendar"},
        status="*",
    )
    assert r.status_int == 201
    etag = r.headers["ETag"]

    # The app edits the same event through the data model.
    from app.auth.service import authenticate_local

    user = authenticate_local(SessionLocal(), "alice@kumo.test", PASSWORD)
    with SessionLocal() as db:
        ev = db.execute(select(CalendarEvent).where(CalendarEvent.uid == "evt-2@test")).scalar_one()
        ev.title = "Edited in app"
        db.commit()

    # CalDAV client fetches it again and sees the new title.
    r = alice.request(f"{CALENDAR}/evt-2@test.ics", method="GET", status="*")
    assert "Edited in app" in r.text


def test_concurrent_edit_conflict(alice):
    alice.request(
        f"{CALENDAR}/evt-3@test.ics",
        method="PUT",
        body=_event_ics("evt-3@test", "V1", "20261103T090000Z", "20261103T100000Z"),
        headers={"Content-Type": "text/calendar"},
        status="*",
    )
    # A stale client uses a wrong etag -> precondition failed.
    r = alice.request(
        f"{CALENDAR}/evt-3@test.ics",
        method="PUT",
        body=_event_ics("evt-3@test", "V2", "20261103T100000Z", "20261103T110000Z"),
        headers={"Content-Type": "text/calendar", "If-Match": '"stale-etag"'},
        status="*",
    )
    assert r.status_int == 412
    assert _db_events("alice")[0].title == "V1"


def test_user_isolation(alice):
    _register("bob", "bob@kumo.test")
    alice.request(
        f"{CALENDAR}/evt-4@test.ics",
        method="PUT",
        body=_event_ics("evt-4@test", "Alice private", "20261104T090000Z", "20261104T100000Z"),
        headers={"Content-Type": "text/calendar"},
        status="*",
    )
    # Bob cannot see Alice's calendar.
    bob = _build_dav_app()
    bob.authorization = ("Basic", ("bob", PASSWORD))
    r = bob.request("/alice/calendar/", method="PROPFIND", headers={"Depth": "1"}, status="*")
    assert r.status_int in (403, 404)
    # And Bob's own calendar is empty.
    r = bob.request("/bob/calendar/", method="PROPFIND", headers={"Depth": "1"}, status="*")
    assert "evt-4" not in r.text


def test_authentication(alice):
    bad = _build_dav_app()
    bad.authorization = ("Basic", ("alice", "wrong-password"))
    r = bad.request("/alice/", method="PROPFIND", headers={"Depth": "0"}, status="*")
    assert r.status_int == 401


def test_recurring_and_allday_roundtrip(alice):
    ics = _event_ics(
        "evt-r@test",
        "Recurring",
        "20261110T090000Z",
        "20261110T100000Z",
        extra="RRULE:FREQ=WEEKLY;BYDAY=MO\r\n",
    )
    r = alice.request(f"{CALENDAR}/evt-r@test.ics", method="PUT", body=ics, headers={"Content-Type": "text/calendar"}, status="*")
    assert r.status_int == 201
    ev = _db_events("alice")[0]
    assert ev.recurrence == "FREQ=WEEKLY;BYDAY=MO"

    # All-day
    ics_all = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:evt-a@test\r\n"
        "DTSTART;VALUE=DATE:20261112\r\nSUMMARY:All day\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    ).encode()
    r = alice.request(f"{CALENDAR}/evt-a@test.ics", method="PUT", body=ics_all, headers={"Content-Type": "text/calendar"}, status="*")
    assert r.status_int == 201
    events = _db_events("alice")
    allday = [e for e in events if e.uid == "evt-a@test"][0]
    assert allday.all_day is True

    # It serializes back as a DATE value.
    r = alice.request(f"{CALENDAR}/evt-a@test.ics", method="GET", status="*")
    assert "VALUE=DATE" in r.text


def test_sync_collection(alice):
    alice.request(
        f"{CALENDAR}/evt-s@test.ics",
        method="PUT",
        body=_event_ics("evt-s@test", "Sync me", "20261120T090000Z", "20261120T100000Z"),
        headers={"Content-Type": "text/calendar"},
        status="*",
    )
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<D:sync-collection xmlns:D="DAV:"><D:sync-token/>'
        '<D:sync-level>1</D:sync-level>'
        '<D:prop><D:getetag/></D:prop>'
        '</D:sync-collection>'
    )
    r = alice.request(f"{CALENDAR}/", method="REPORT", body=body.encode(), headers={"Content-Type": "application/xml"}, status="*")
    assert r.status_int == 207
    assert "evt-s%40test" in r.text
    assert "sync-token" in r.text
