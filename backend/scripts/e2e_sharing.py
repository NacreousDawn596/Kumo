"""End-to-end sharing/invitation test against a running backend.

Run with:  cd backend && uv run python scripts/e2e_sharing.py
Uses the mock users seeded by scripts/seed_users.py plus a SchoolApp owner.
"""

from __future__ import annotations

import httpx

BASE = "http://127.0.0.1:8000"


def client() -> httpx.Client:
    return httpx.Client(base_url=BASE, timeout=30)


def login(c: httpx.Client, email: str, password: str) -> dict:
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def register(c: httpx.Client, email: str, username: str, name: str) -> dict:
    r = c.post(
        "/api/auth/register",
        json={"email": email, "username": username, "display_name": name, "password": "mock-password-123"},
    )
    return r.json()


def main() -> None:
    # Owner = the SchoolApp-linked user; use a local admin for determinism.
    owner = client()
    try:
        owner_user = login(owner, "amira.benali@example.com", "mock-password-123")
    except Exception:
        owner_user = register(owner, "amira.benali@example.com", "amira", "Amira Benali")
        owner_user = login(owner, "amira.benali@example.com", "mock-password-123")
    print(f"owner: {owner_user['display_name']}")

    # --- 1. Mock users appear in search ---
    r = owner.get("/api/knowledge/search", params={"q": "youssef"})
    users = [x for x in r.json() if x["type"] == "user"]
    print(f"search 'youssef' -> {len(users)} user(s):", [u["title"] for u in users])

    # --- 2. Group + invite link + join request + approval ---
    g = owner.post("/api/groups", json={"name": "Mechanics Study Group"}).json()
    group_id = g["id"]
    link = owner.post(f"/api/groups/{group_id}/invite-link").json()
    print("group invite link:", link["url"])

    member = client()
    try:
        login(member, "youssef.elidrissi@example.com", "mock-password-123")
    except Exception:
        register(member, "youssef.elidrissi@example.com", "youssef", "Youssef El Idrissi")
        login(member, "youssef.elidrissi@example.com", "mock-password-123")

    req = member.post(f"/api/groups/join/{link['token']}")
    print("join request status:", req.status_code, req.json().get("requested"))

    # Owner approves the pending request.
    invites = owner.get(f"/api/groups/{group_id}/invitations").json()
    pending = [i for i in invites if i["status"] == "pending"]
    print("pending requests:", len(pending))
    for p in pending:
        owner.post(f"/api/groups/requests/{p['id']}/approve")

    # Member now sees the group + conversation.
    convs = member.get("/api/conversations").json()
    gc = [c for c in convs if c["group_id"] == group_id]
    print("member group conversations:", len(gc))
    if gc:
        send = member.post(f"/api/conversations/{gc[0]['id']}/messages", json={"body": "hello from Youssef"})
        print("member message send:", send.status_code)

    # --- 3. File public/private ---
    up = owner.post(
        "/api/vault/files",
        files={"file": ("syllabus.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"name": "syllabus.pdf"},
    )
    file_id = up.json()["id"]
    pub = owner.post(f"/api/vault/files/{file_id}/make-public").json()
    print("public url:", pub["url"])

    anon = client()  # no auth
    meta = anon.get(f"/api{pub['url']}")
    print("anon metadata status:", meta.status_code, meta.json().get("name"))
    content = anon.get(f"/api{pub['url']}/content")
    print("anon content status:", content.status_code)

    # Make private again — anon should now be denied.
    owner.post(f"/api/vault/files/{file_id}/make-private")
    meta2 = anon.get(f"/api{pub['url']}")
    print("anon metadata after private:", meta2.status_code)

    # --- 4. Session invite link ---
    s = owner.post("/api/sessions", json={"name": "Chapter 5 Revision"}).json()
    s_link = owner.post(f"/api/sessions/{s['id']}/invite-link").json()
    join = member.post(f"/api/sessions/join/{s_link['token']}")
    print("session join:", join.status_code, "members:", len(join.json().get("members", [])))


if __name__ == "__main__":
    main()
