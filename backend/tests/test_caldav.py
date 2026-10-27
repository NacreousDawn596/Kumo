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


def test_schoolapp_user_gets_caldav_password():
    from app.auth.service import find_or_create_for_identity, rotate_caldav_password

    with SessionLocal() as db:
        user = find_or_create_for_identity(
            db, provider="schoolapp", subject="SA-1", email="s1@kumo.test", display_name="S1"
        )
        # Provisioned with a password hash so CalDAV Basic auth works.
        assert user.password_hash is not None
        first = user.password_hash
        # Rotated on every login.
        rotate_caldav_password(db, user)
        assert user.password_hash != first


def test_caldav_password_token_authenticates():
    from app.auth.service import find_or_create_for_identity, rotate_caldav_password

    with SessionLocal() as db:
        user = find_or_create_for_identity(
            db, provider="schoolapp", subject="SA-2", email="s2@kumo.test", display_name="S2"
        )
        token = rotate_caldav_password(db, user)
        username = user.username

    dav = _build_dav_app()
    dav.authorization = ("Basic", (username, token))
    r = dav.request(f"/{username}/", method="PROPFIND", headers={"Depth": "0"}, status="*")
    assert r.status_int == 207


def test_caldav_password_endpoint_returns_plaintext(client):
    from app.auth.service import rotate_caldav_password
    from app.models import User

    client.post(
        "/api/auth/register",
        json={"email": "cal@example.com", "username": "caluser", "display_name": "Cal", "password": PASSWORD},
    )
    r = client.post("/api/users/me/caldav-password")
    assert r.status_code == 200
    body = r.json()
    assert len(body["password"]) == 32
    assert body["username"] == "caluser"

    # The returned token now authenticates against CalDAV.
    dav = _build_dav_app()
    dav.authorization = ("Basic", ("caluser", body["password"]))
    rr = dav.request("/caluser/", method="PROPFIND", headers={"Depth": "0"}, status="*")
    assert rr.status_int == 207


# --- Time zones --------------------------------------------------------------------

def _put(alice, href: str, body: str):
    return alice.request(
        href, method="PUT", body=body.encode(), headers={"Content-Type": "text/calendar"}, status="*"
    )


def test_timezone_roundtrip_dst(alice):
    # Summer (EDT, UTC-4): 9:00 AM local == 13:00 UTC.
    ics = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        "UID:tz-1@test\r\nDTSTART;TZID=America/New_York:20260701T090000\r\n"
        "DTEND;TZID=America/New_York:20260701T100000\r\nSUMMARY:Summer\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    r = _put(alice, f"{CALENDAR}/tz-1@test.ics", ics)
    assert r.status_int in (200, 201, 204)

    with SessionLocal() as db:
        ev = db.execute(select(CalendarEvent).where(CalendarEvent.uid == "tz-1@test")).scalar_one()
    assert ev.timezone == "America/New_York"
    assert ev.start_at.hour == 13  # stored naive-UTC: 9 AM EDT == 13 UTC

    # The stored event re-exports with TZID + a VTIMEZONE, preserving 9 AM local.
    r = alice.request(f"{CALENDAR}/tz-1@test.ics", method="GET", status="*")
    assert "TZID=America/New_York:20260701T090000" in r.text
    assert "BEGIN:VTIMEZONE" in r.text
    assert "TZID:America/New_York" in r.text

    # Winter (EST, UTC-5): 9:00 AM local == 14:00 UTC.
    ics2 = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        "UID:tz-2@test\r\nDTSTART;TZID=America/New_York:20260115T090000\r\n"
        "SUMMARY:Winter\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    _put(alice, f"{CALENDAR}/tz-2@test.ics", ics2)
    with SessionLocal() as db:
        ev2 = db.execute(select(CalendarEvent).where(CalendarEvent.uid == "tz-2@test")).scalar_one()
    assert ev2.start_at.hour == 14  # 9 AM EST == 14 UTC
    r = alice.request(f"{CALENDAR}/tz-2@test.ics", method="GET", status="*")
    assert "TZID=America/New_York:20260115T090000" in r.text


# --- Recurrence exceptions ---------------------------------------------------------

def _recurring_master() -> str:
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        "UID:rec-1@test\r\nDTSTART:20261102T090000Z\r\n"
        "RRULE:FREQ=WEEKLY\r\nEXDATE:20261109T090000Z\r\n"
        "SUMMARY:Weekly\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )


def test_recurrence_exceptions_roundtrip(alice):
    from app.models import CalendarEventOverride

    r = _put(alice, f"{CALENDAR}/rec-1@test.ics", _recurring_master())
    assert r.status_int in (200, 201, 204)

    # Moved occurrence.
    moved = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        "UID:rec-1@test\r\nRECURRENCE-ID:20261116T090000Z\r\n"
        "DTSTART:20261117T100000Z\r\nDTEND:20261117T110000Z\r\n"
        "SUMMARY:Weekly (moved)\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    _put(alice, f"{CALENDAR}/rec-1@test-20261116T090000Z.ics", moved)

    # Cancelled occurrence.
    cancelled = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        "UID:rec-1@test\r\nRECURRENCE-ID:20261123T090000Z\r\n"
        "DTSTART:20261123T090000Z\r\nSTATUS:CANCELLED\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    _put(alice, f"{CALENDAR}/rec-1@test-20261123T090000Z.ics", cancelled)

    with SessionLocal() as db:
        master = db.execute(select(CalendarEvent).where(CalendarEvent.uid == "rec-1@test")).scalar_one()
        assert master.recurrence == "FREQ=WEEKLY"
        assert len(master.exdates or "") > 0
        overrides = db.execute(
            select(CalendarEventOverride).where(CalendarEventOverride.event_id == master.id)
        ).scalars().all()
        assert len(overrides) == 2
        by_rid = {o.recurrence_id.replace(tzinfo=None).isoformat(): o for o in overrides}

    assert "2026-11-16T09:00:00" in by_rid
    assert "2026-11-23T09:00:00" in by_rid
    moved_ov = by_rid["2026-11-16T09:00:00"]
    assert moved_ov.cancelled is False
    assert moved_ov.start_at.hour == 10  # moved to 10:00 UTC
    cancelled_ov = by_rid["2026-11-23T09:00:00"]
    assert cancelled_ov.cancelled is True

    # Round-trip via CalDAV GET.
    r = alice.request(f"{CALENDAR}/rec-1@test.ics", method="GET", status="*")
    assert "RRULE:FREQ=WEEKLY" in r.text
    assert "EXDATE:20261109T090000Z" in r.text

    r = alice.request(f"{CALENDAR}/rec-1@test-20261116T090000Z.ics", method="GET", status="*")
    assert "RECURRENCE-ID:20261116T090000Z" in r.text
    assert "SUMMARY:Weekly (moved)" in r.text

    r = alice.request(f"{CALENDAR}/rec-1@test-20261123T090000Z.ics", method="GET", status="*")
    assert "STATUS:CANCELLED" in r.text

    # PROPFIND lists three items (master + 2 overrides); "@" is percent-encoded.
    r = alice.request(f"{CALENDAR}/", method="PROPFIND", headers={"Depth": "1"}, status="*")
    assert "rec-1%40test.ics" in r.text
    assert "rec-1%40test-20261116T090000Z" in r.text
    assert "rec-1%40test-20261123T090000Z" in r.text


def test_recurrence_override_delete(alice):
    from app.models import CalendarEventOverride

    _put(alice, f"{CALENDAR}/rec-2@test.ics", _recurring_master().replace("rec-1", "rec-2"))
    _put(
        alice,
        f"{CALENDAR}/rec-2@test-20261116T090000Z.ics",
        (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
            "UID:rec-2@test\r\nRECURRENCE-ID:20261116T090000Z\r\n"
            "DTSTART:20261117T100000Z\r\nSUMMARY:Moved\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        ),
    )
    # Delete just the override.
    r = alice.request(f"{CALENDAR}/rec-2@test-20261116T090000Z.ics", method="DELETE", status="*")
    assert r.status_int == 200

    with SessionLocal() as db:
        master = db.execute(select(CalendarEvent).where(CalendarEvent.uid == "rec-2@test")).scalar_one()
        overrides = db.execute(
            select(CalendarEventOverride).where(CalendarEventOverride.event_id == master.id)
        ).scalars().all()
    assert overrides == []  # override removed, master still present


# --- Calendar properties -----------------------------------------------------------

def test_calendar_properties_persist(alice):
    proppatch = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<D:propertyupdate xmlns:D="DAV:" xmlns:I="http://apple.com/ns/ical/">'
        "<D:set><D:prop>"
        "<D:displayname>My Personal Calendar</D:displayname>"
        "<I:calendar-color>#FF0000FF</I:calendar-color>"
        "</D:prop></D:set>"
        "</D:propertyupdate>"
    )
    r = alice.request(f"{CALENDAR}/", method="PROPPATCH", body=proppatch.encode(), headers={"Content-Type": "application/xml"}, status="*")
    assert r.status_int == 207

    # PROPFIND returns the persisted values.
    r = alice.request(
        f"{CALENDAR}/",
        method="PROPFIND",
        headers={"Depth": "0"},
        body=(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<D:propfind xmlns:D="DAV:" xmlns:I="http://apple.com/ns/ical/">'
            "<D:prop><D:displayname/><I:calendar-color/></D:prop>"
            "</D:propfind>"
        ).encode(),
        status="*",
    )
    assert r.status_int == 207
    assert "My Personal Calendar" in r.text
    assert "#FF0000FF" in r.text


def test_rest_export_preserves_exceptions(client):
    from datetime import timezone

    from app.models import CalendarEventOverride

    client.post(
        "/api/auth/register",
        json={"email": "exp@example.com", "username": "expuser", "display_name": "Exp", "password": PASSWORD},
    )
    with SessionLocal() as db:
        u = db.execute(select(User).where(User.username == "expuser")).scalar_one()
        ev = CalendarEvent(
            organizer_id=u.id, title="Recurring", recurrence="FREQ=WEEKLY",
            start_at=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc),
            exdates='["2026-11-09T09:00:00+00:00"]',
        )
        db.add(ev)
        db.flush()
        db.add(CalendarEventOverride(
            event_id=ev.id,
            recurrence_id=datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc),
            start_at=datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc),
            title="Moved instance",
        ))
        db.commit()

    r = client.get("/api/calendar/export.ics")
    assert r.status_code == 200
    assert "RRULE:FREQ=WEEKLY" in r.text
    assert "EXDATE:20261109T090000Z" in r.text
    assert "RECURRENCE-ID:20261116T090000Z" in r.text
    assert "SUMMARY:Moved instance" in r.text

    # Re-import into a fresh user and verify the recurrence + override survive.
    client.post("/api/auth/register", json={"email": "imp@example.com", "username": "impuser", "display_name": "Imp", "password": PASSWORD})
    r2 = client.post("/api/calendar/import", json={"content": r.text})
    assert r2.status_code == 200
    assert r2.json()["imported"] == 1

    with SessionLocal() as db:
        u2 = db.execute(select(User).where(User.username == "impuser")).scalar_one()
        imported = db.execute(select(CalendarEvent).where(CalendarEvent.organizer_id == u2.id)).scalar_one()
        assert imported.recurrence == "FREQ=WEEKLY"
        assert "2026-11-09T09:00:00" in (imported.exdates or "")
        ovs = db.execute(select(CalendarEventOverride).where(CalendarEventOverride.event_id == imported.id)).scalars().all()
        assert len(ovs) == 1
        assert ovs[0].title == "Moved instance"



