"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


def pytest_configure(config: pytest.Config) -> None:
    """Ensure required settings are present before app.config is imported."""
    os.environ.setdefault("APP_SECRET_KEY", "test-secret-key")
    os.environ.setdefault("APP_DEBUG", "true")


@pytest.fixture
def client() -> TestClient:
    from app.main import app  # imported after pytest_configure sets env vars

    return TestClient(app)
