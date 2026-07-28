"""Application configuration.

All environment-dependent or secret values are read from environment
variables (via a .env file in development) — never hardcoded, per CLAUDE.md.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="APP_",
        extra="ignore",
        # Needed so ANTHROPIC_API_KEY (below) can be passed as the
        # `anthropic_api_key` kwarg directly (e.g. from tests) in addition to
        # its env-var alias - without this, pydantic-settings only accepts
        # the alias for a field that declares one.
        populate_by_name=True,
    )

    app_name: str = "Phishing Email Analyzer"
    debug: bool = False
    secret_key: str

    #: "development" or "production" — gates dev-only conveniences (e.g. the
    #: interactive API docs, and the Secure flag on cookies) without
    #: duplicating a whole settings hierarchy.
    environment: str = "development"

    #: Caps raw email size (pasted or uploaded) accepted by the /upload
    #: endpoint, bounding memory use during parsing (Phase 3 "safe parsing").
    max_email_upload_bytes: int = 10_000_000

    # --- PostgreSQL / SQLAlchemy (Phase 5) ---
    #: Full SQLAlchemy connection string, e.g.
    #: "postgresql+psycopg2://user:pass@host:5432/dbname" — must start with
    #: "postgresql" (enforced below); never sqlite, to match the production
    #: database (see CLAUDE.md/TASKS.md Phase 5).
    database_url: str
    #: psycopg2 tries every resolved address (IPv6 then IPv4) with no
    #: timeout by default, which can turn one unreachable database into a
    #: multi-second stall per request - keep this short so a down/
    #: unreachable database fails fast (persistence is best-effort; see
    #: app/api/v1/upload.py, app/auth/router.py). Must be an int - psycopg2's
    #: connect_timeout DSN parameter rejects a float (e.g. "3.0") outright.
    database_connect_timeout_seconds: int = 3

    # --- Active Directory / LDAPS (Phase 6) ---
    #: e.g. "ldaps://ad.example.local:636" — must be ldaps://, never plain
    #: ldap://, per CLAUDE.md's "LDAPS only" requirement; enforced below.
    ldap_server_uri: str
    #: Service account used only to search for a user's DN — never used to
    #: validate a login password (that always happens via a bind-as-user).
    ldap_bind_dn: str
    ldap_bind_password: str
    ldap_user_search_base_dn: str
    #: DN of the AD group a user must belong to (directly or via nested
    #: groups - see app/auth/ldap_backend.py) to be authorized to log in.
    ldap_required_group_dn: str
    ldap_user_login_attribute: str = "sAMAccountName"
    ldap_connect_timeout_seconds: float = 5.0
    #: Caps how many levels of nested (parent-of-parent) group membership
    #: are walked before giving up - bounds worst-case LDAP round-trips and
    #: guards against a misconfigured/cyclic group graph.
    ldap_group_membership_max_depth: int = 6

    # --- Session cookies (Phase 6) ---
    session_max_age_seconds: int = 28_800  # 8 hours

    # --- Claude API / AI explanations (Phase 7) ---
    #: Read from the bare ANTHROPIC_API_KEY env var (the SDK's own convention),
    #: not APP_ANTHROPIC_API_KEY - this is the same variable a developer would
    #: set for any Anthropic SDK usage. Deliberately optional: the app must
    #: start and email analysis must keep working with no key configured
    #: (see CLAUDE.md) - app.ai_analysis.services checks this and returns a
    #: "not configured" result instead of calling the API.
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = "claude-opus-5"
    #: Explanations are a few sentences of prose, not a long-form document -
    #: capped low so a misbehaving prompt/response can't run up cost/latency.
    anthropic_max_tokens: int = 500
    anthropic_timeout_seconds: float = 15.0

    @field_validator("ldap_server_uri")
    @classmethod
    def _require_ldaps_scheme(cls, value: str) -> str:
        if not value.lower().startswith("ldaps://"):
            raise ValueError("APP_LDAP_SERVER_URI must use the ldaps:// scheme (LDAPS only)")
        return value

    @field_validator("database_url")
    @classmethod
    def _require_postgresql_scheme(cls, value: str) -> str:
        if not value.lower().startswith("postgresql"):
            raise ValueError(
                "APP_DATABASE_URL must be a postgresql:// (or postgresql+driver://) URL"
            )
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read once per process)."""
    return Settings()  # type: ignore[call-arg]  # secret_key comes from env/.env, not this call
