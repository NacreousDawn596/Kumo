"""Test fixtures: isolated environment and database."""

import os
import tempfile

# Set environment BEFORE importing app modules so the Settings singleton and
# engine are created with test values.
_tmp = tempfile.mkdtemp(prefix="kumo-test-")
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["STORAGE_PATH"] = f"{_tmp}/storage"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["COOKIE_SECURE"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def make_user(client):
    def _make(email: str, username: str, display_name: str, password: str = "correct-horse-battery-staple"):
        resp = client.post(
            "/api/auth/register",
            json={"email": email, "username": username, "display_name": display_name, "password": password},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _make
