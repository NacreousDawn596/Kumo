"""Identity provider abstraction.

Kumo's preferred identity provider is SchoolApp. Because the concrete
SchoolApp OIDC/OAuth contract (authorization endpoint, token endpoint, JWKS,
and subject claim) is provider-specific and not yet documented here, this
module defines a clean adapter boundary plus:

  * a working ``local`` provider (email + password, Argon2id) for development
    and for tests, and
  * a ``schoolapp`` provider that is an honest, documented scaffold: it raises
    a clear "not configured" error until the provider endpoints are supplied.

Nothing here scrapes credentials or invents undocumented endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings


class ProviderNotConfigured(Exception):
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
    """Documented scaffold. See infra/schoolapp-worker for the integration."""

    name = "schoolapp"

    def verify_assertion(self, assertion: str) -> VerifiedIdentity:
        if not (settings.schoolapp_issuer and settings.schoolapp_jwks_url):
            raise ProviderNotConfigured(
                "SchoolApp is not configured. Set SCHOOLAPP_ISSUER, "
                "SCHOOLAPP_JWKS_URL, and related settings, or use the local provider."
            )
        # Real implementation: validate a JWT assertion's signature against the
        # provider JWKS, then check issuer == schoolapp_issuer, audience ==
        # schoolapp_audience, exp is in the future, and reject replays (jti
        # cache). Extract the stable subject identifier.
        raise ProviderNotConfigured(
            "SchoolApp assertion verification is not yet implemented; the JWKS "
            "validation contract requires the provider's documented endpoints."
        )


def get_provider(name: str | None = None) -> IdentityProvider:
    provider_name = name or settings.auth_provider
    if provider_name == "schoolapp":
        return SchoolAppProvider()
    return LocalProvider()
