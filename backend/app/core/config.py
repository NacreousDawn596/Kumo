"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Kumo"
    environment: str = "development"
    debug: bool = False

    # Base URL / hosting
    public_base_url: str = "http://localhost:8000"
    frontend_origin: str = "http://localhost:5173"
    allowed_origins: str = "http://localhost:5173,http://localhost:4173"

    # Database
    database_url: str = "sqlite:///./data/kumo.db"

    # Storage (large binary contents kept outside SQLite)
    storage_path: str = "./data/storage"

    # Security
    secret_key: str = "change-me-in-production"
    session_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 days refresh
    access_token_ttl_seconds: int = 60 * 15  # 15 minutes

    # Auth provider
    auth_provider: str = "local"  # "local" | "schoolapp"

    # SchoolApp (documented scaffold — real endpoints TBD with provider)
    schoolapp_issuer: str = ""
    schoolapp_client_id: str = ""
    schoolapp_client_secret: str = ""
    schoolapp_authorize_url: str = ""
    schoolapp_token_url: str = ""
    schoolapp_jwks_url: str = ""
    schoolapp_audience: str = ""
    # Shared secret with the Cloudflare Worker that verifies SchoolApp identity.
    # The Worker signs a short-lived assertion with this HMAC key; the backend
    # verifies it. Must match the WORKER's SCHOOLAPP_WORKER_SECRET.
    schoolapp_worker_secret: str = ""
    schoolapp_worker_issuer: str = "schoolapp-worker"
    schoolapp_worker_audience: str = "kumo"

    # Limits
    max_upload_bytes: int = 50 * 1024 * 1024  # 50 MB
    default_storage_quota_bytes: int = 500 * 1024 * 1024  # 500 MB per user
    max_message_bytes: int = 64 * 1024

    # Web Push (VAPID) — set keys to enable browser push notifications.
    # Generate: `openssl ecparam -genkey -name prime256v1 -noout -out vapid_private.pem`
    # and derive the public key; or use pywebpush's vapid helper.
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@kumo.example.com"

    # LiveKit (SFU for group audio). Leave empty to disable group calls.
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # TURN relay (for WebRTC behind restrictive NATs). Comma-separated URIs.
    turn_uris: str = ""
    turn_username: str = ""
    turn_credential: str = ""

    # Cookies
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    @property
    def allowed_origin_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
