"""Seed the database with mock users for testing (dev only).

Usage:
    cd backend && uv run python scripts/seed_users.py

Creates a set of demo users with a shared password. Safe to run repeatedly
(uses upsert semantics — existing emails/usernames are skipped).
"""

from __future__ import annotations

from sqlalchemy import select

from app.auth.service import register_local_user
from app.core.database import SessionLocal
from app.models import User

MOCK_USERS = [
    ("amira.benali@example.com", "amira", "Amira Benali"),
    ("youssef.elidrissi@example.com", "youssef", "Youssef El Idrissi"),
    ("sara.amrani@example.com", "sara", "Sara Amrani"),
    ("omar.berrada@example.com", "omar", "Omar Berrada"),
    ("lina.chakir@example.com", "lina", "Lina Chakir"),
    ("hamza.daoudi@example.com", "hamza", "Hamza Daoudi"),
    ("nadia.essaidi@example.com", "nadia", "Nadia Essaidi"),
    ("karim.fassi@example.com", "karim", "Karim Fassi"),
    ("salma.ghazi@example.com", "salma", "Salma Ghazi"),
    ("mehdi.hadri@example.com", "mehdi", "Mehdi Hadri"),
]

PASSWORD = "mock-password-123"


def main() -> None:
    db = SessionLocal()
    created = 0
    skipped = 0
    try:
        for email, username, display_name in MOCK_USERS:
            exists = db.execute(
                select(User).where((User.email == email) | (User.username == username))
            ).scalar_one_or_none()
            if exists:
                skipped += 1
                continue
            register_local_user(
                db, email=email, username=username, display_name=display_name, password=PASSWORD
            )
            created += 1
            print(f"created {username} ({email})")
    finally:
        db.close()
    print(f"\nDone: {created} created, {skipped} skipped.")
    print(f"All mock users share the password: {PASSWORD}")


if __name__ == "__main__":
    main()
