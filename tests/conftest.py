"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


def pytest_configure(config: pytest.Config) -> None:
    """Ensure required settings are present before app.config is imported."""
    os.environ.setdefault("APP_SECRET_KEY", "test-secret-key")
    os.environ.setdefault("APP_DEBUG", "true")
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
