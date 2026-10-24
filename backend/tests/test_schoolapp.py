"""SchoolApp assertion verification tests."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import sign_hmac_token, verify_hmac_token
from app.main import app


def test_hmac_token_roundtrip():
    secret = "test-shared-secret"
    token = sign_hmac_token({"sub": "12345", "email": "a@b.c"}, secret, 120)
    payload = verify_hmac_token(token, secret)
    assert payload["sub"] == "12345"


def test_hmac_token_tamper_rejected():
    secret = "test-shared-secret"
    token = sign_hmac_token({"sub": "12345"}, secret, 120)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    try:
        verify_hmac_token(tampered, secret)
        assert False, "should have raised"
    except ValueError:
        pass


def test_schoolapp_assert_creates_session():
    old = settings.schoolapp_worker_secret
    settings.schoolapp_worker_secret = "worker-shared-secret"
    try:
        client = TestClient(app)
        assertion = sign_hmac_token(
            {
                "sub": "SA-2024-0001",
                "email": "student@ensam.umi.ac.ma",
                "name": "SchoolApp Student",
                "iss": settings.schoolapp_worker_issuer,
                "aud": settings.schoolapp_worker_audience,
            },
            "worker-shared-secret",
            120,
        )
        resp = client.post("/api/auth/schoolapp/assert", json={"assertion": assertion})
        assert resp.status_code == 200, resp.text
        assert resp.json()["email"] == "student@ensam.umi.ac.ma"
        # A session is established.
        assert client.get("/api/auth/me").status_code == 200
    finally:
        settings.schoolapp_worker_secret = old


def test_schoolapp_assert_rejects_bad_secret():
    old = settings.schoolapp_worker_secret
    settings.schoolapp_worker_secret = "correct-secret"
    try:
        client = TestClient(app)
        # Signed with the WRONG secret.
        assertion = sign_hmac_token(
            {"sub": "x", "iss": settings.schoolapp_worker_issuer, "aud": settings.schoolapp_worker_audience},
            "wrong-secret",
            120,
        )
        resp = client.post("/api/auth/schoolapp/assert", json={"assertion": assertion})
        assert resp.status_code == 401
    finally:
        settings.schoolapp_worker_secret = old


def test_schoolapp_assert_unconfigured_returns_501():
    old = settings.schoolapp_worker_secret
    settings.schoolapp_worker_secret = ""
    try:
        client = TestClient(app)
        resp = client.post("/api/auth/schoolapp/assert", json={"assertion": "whatever"})
        assert resp.status_code == 501
    finally:
        settings.schoolapp_worker_secret = old
