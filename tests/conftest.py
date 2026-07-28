"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


def pytest_configure(config: pytest.Config) -> None:
    """Ensure required settings are present before app.config is imported."""
    os.environ.setdefault("APP_SECRET_KEY", "test-secret-key")
    os.environ.setdefault("APP_DEBUG", "true")
    # Placeholder-only DB URL so Settings() construction succeeds without a
    # real database. Deliberately unreachable (nothing listens on
    # 127.0.0.1:5432 in this test environment) - persistence call sites are
    # designed to be best-effort and swallow the resulting connection error
    # (see app/api/v1/upload.py, app/auth/router.py), and tests that need a
    # *real* Postgres (tests/integration/test_database.py, test_dashboard.py,
    # test_alembic_migrations.py) read TEST_DATABASE_URL instead and skip
    # themselves when it's unset/unreachable. A literal IP (not "localhost")
    # avoids also trying the ::1 (IPv6) resolution, and a 1s timeout (vs the
    # 3s production default) keeps the many DB-touching tests fast - both
    # only affect how quickly THIS placeholder fails, never real deployments.
    os.environ.setdefault(
        "APP_DATABASE_URL", "postgresql+psycopg2://test:test@127.0.0.1:5432/test_db_unreachable"
    )
    os.environ.setdefault("APP_DATABASE_CONNECT_TIMEOUT_SECONDS", "1")
    # Placeholder-only LDAP config so Settings() construction succeeds without
    # real AD credentials - every LDAP-touching test mocks app.auth.ldap_backend
    # directly rather than using these values to contact a real server.
    os.environ.setdefault("APP_LDAP_SERVER_URI", "ldaps://ad.test.invalid:636")
    os.environ.setdefault("APP_LDAP_BIND_DN", "CN=svc-test,DC=test,DC=invalid")
    os.environ.setdefault("APP_LDAP_BIND_PASSWORD", "test-bind-password")
    os.environ.setdefault("APP_LDAP_USER_SEARCH_BASE_DN", "OU=Users,DC=test,DC=invalid")
    os.environ.setdefault("APP_LDAP_REQUIRED_GROUP_DN", "CN=Required,OU=Groups,DC=test,DC=invalid")


@pytest.fixture
def client() -> TestClient:
    from app.main import app  # imported after pytest_configure sets env vars

    return TestClient(app)
