"""Application configuration.

All environment-dependent or secret values are read from environment
variables (via a .env file in development) — never hardcoded, per CLAUDE.md.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="APP_", extra="ignore"
    )

    app_name: str = "Phishing Email Analyzer"
    debug: bool = False
    secret_key: str

    #: "development" or "production" — gates dev-only conveniences (e.g. the
    #: interactive API docs) without duplicating a whole settings hierarchy.
    environment: str = "development"

    #: Caps raw email size (pasted or uploaded) accepted by the /upload
    #: endpoint, bounding memory use during parsing (Phase 3 "safe parsing").
    max_email_upload_bytes: int = 10_000_000


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read once per process)."""
    return Settings()  # type: ignore[call-arg]  # secret_key comes from env/.env, not this call
