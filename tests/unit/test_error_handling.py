"""Tests for HTTP and unhandled-exception error rendering."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_404_renders_error_page(client: TestClient) -> None:
    response = client.get("/this-route-does-not-exist")

    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "404" in response.text


def test_unhandled_exception_hides_details_when_debug_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main as main_module

    monkeypatch.setattr(main_module.settings, "debug", False)

    @main_module.app.get("/_boom_debug_off")
    def _boom_debug_off() -> None:
        raise ValueError("sensitive internal detail")

    # Starlette's ServerErrorMiddleware re-raises after our handler runs (so a real
    # server's process-level logging still sees it) — raise_server_exceptions=False
    # tells TestClient to return the generated response instead of propagating that.
    with TestClient(main_module.app, raise_server_exceptions=False) as unsafe_client:
        response = unsafe_client.get("/_boom_debug_off")

    assert response.status_code == 500
    assert "sensitive internal detail" not in response.text
    assert "An unexpected error occurred." in response.text


def test_unhandled_exception_shows_details_when_debug_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main as main_module

    monkeypatch.setattr(main_module.settings, "debug", True)

    @main_module.app.get("/_boom_debug_on")
    def _boom_debug_on() -> None:
        raise ValueError("sensitive internal detail")

    with TestClient(main_module.app, raise_server_exceptions=False) as unsafe_client:
        response = unsafe_client.get("/_boom_debug_on")

    assert response.status_code == 500
    assert "sensitive internal detail" in response.text
