"""Tests for the base Jinja2 + Bootstrap layout."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_index_renders_html(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Phishing Email Analyzer" in response.text
    assert "bootstrap" in response.text.lower()
