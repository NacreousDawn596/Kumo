"""Identity provider abstraction.

Kumo authenticates students through SchoolApp. The SchoolApp Cloudflare Worker
verifies the student's credentials and returns a short-lived HMAC-signed
assertion, which this module verifies (signature, issuer, audience, expiry).
A local email/password provider backs the backend API and tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings


class ProviderNotConfigured(Exception):
    pass


class InvalidAssertion(Exception):
    pass


@dataclass
class VerifiedIdentity:
    provider: str
    subject: str
    email: str | None
    display_name: str | None


class IdentityProvider(Protocol):
    name: str

    def verify_assertion(self, assertion: str) -> VerifiedIdentity: ...


class LocalProvider:
    name = "local"

    def verify_assertion(self, assertion: str) -> VerifiedIdentity:
        # Local flow is handled directly in the auth service via email/password;
        # this provider exists for interface symmetry and is intentionally unused
        # for programmatic assertion verification.
        raise ProviderNotConfigured("local provider does not verify assertions")


class SchoolAppProvider:
    """Verifies a short-lived assertion signed by the SchoolApp Worker.

    The Worker logs the student into SchoolApp (via schoolapp.js), retrieves
    the stable subject identifier, and returns an HMAC-signed assertion. The
    backend verifies the signature, issuer, audience, and expiry — it never
    handles or stores the student's SchoolApp password.
    """

    name = "schoolapp"

    def verify_assertion(self, assertion: str) -> VerifiedIdentity:
        if not settings.schoolapp_worker_secret:
            raise ProviderNotConfigured(
                "SchoolApp is not configured. Set SCHOOLAPP_WORKER_SECRET to the "
                "shared secret used by the Cloudflare Worker."
            )
        from app.core.security import verify_hmac_token

        try:
            payload = verify_hmac_token(assertion, settings.schoolapp_worker_secret)
        except ValueError as exc:
            raise InvalidAssertion(f"Invalid SchoolApp assertion: {exc}") from exc

        if payload.get("iss") != settings.schoolapp_worker_issuer:
            raise InvalidAssertion("SchoolApp assertion issuer mismatch")
        if payload.get("aud") != settings.schoolapp_worker_audience:
            raise InvalidAssertion("SchoolApp assertion audience mismatch")
        subject = payload.get("sub")
        if not subject:
            raise InvalidAssertion("SchoolApp assertion missing subject")
        return VerifiedIdentity(
            provider="schoolapp",
            subject=str(subject),
            email=payload.get("email"),
            display_name=payload.get("name"),
        )


def get_provider(name: str | None = None) -> IdentityProvider:
    provider_name = name or settings.auth_provider
    if provider_name == "schoolapp":
        return SchoolAppProvider()
    return LocalProvider()
