"""Tests for recently added features: sketcher, ICS import, avatar upload."""

from fastapi.testclient import TestClient

from app.main import app

# A minimal 1x1 transparent PNG.
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c63600000020001548e2a60000000"
    "0049454e44ae426082"
)


def _register(client, email, username, name):
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "display_name": name, "password": "correct-horse-battery-staple"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _molfile():
    return "\n".join([
        "Sketch",
        "  Kumo sketcher",
        "",
        "  2  1" + "  0" * 8 + "999 V2000",
        "    1.5000    1.5000    0.0000 " + "C".ljust(3) + " 0" + "  0" * 11,
        "    3.0000    1.5000    0.0000 " + "O".ljust(3) + " 0" + "  0" * 11,
        "  1  2  2  0",
        "M  END",
    ])


def test_chemistry_sketch():
    client = TestClient(app)
    resp = client.post("/api/chemistry/sketch", json={"molfile": _molfile()})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["valid"] is True
    assert data["formula"] == "CH2O"
    assert data["num_atoms"] == 2
    assert data["num_bonds"] == 1


def test_ics_import():
    client = TestClient(app)
    _register(client, "ics@example.com", "icsuser", "ICS User")
    ics = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "BEGIN:VEVENT",
        "UID:abc@test",
        "DTSTART:20261030T100000Z",
        "DTEND:20261030T110000Z",
        "SUMMARY:Imported class",
        "END:VEVENT",
        "END:VCALENDAR",
    ])
    resp = client.post("/api/calendar/import", json={"content": ics})
    assert resp.status_code == 200, resp.text
    assert resp.json()["imported"] == 1

    export = client.get("/api/calendar/export.ics")
    assert "Imported class" in export.text


def test_avatar_upload():
    client = TestClient(app)
    user = _register(client, "avatar@example.com", "avataruser", "Avatar User")
    resp = client.post(
        "/api/users/me/avatar",
        files={"file": ("a.png", PNG_1PX, "image/png")},
    )
    assert resp.status_code == 200, resp.text
    avatar_url = resp.json()["avatar_url"]
    assert avatar_url.startswith(f"/api/users/{user['id']}/avatar")

    # The avatar is served (no auth required, same as a public image URL).
    got = client.get(avatar_url)
    assert got.status_code == 200
