"""Tests for the home page and shared base layout."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_index_renders_html(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Phishing Email Analyzer" in response.text
    assert "bootstrap" in response.text.lower()


def test_index_includes_navbar(client: TestClient) -> None:
    response = client.get("/")

    assert 'class="navbar' in response.text
    assert 'href="/health"' in response.text


def test_index_includes_footer(client: TestClient) -> None:
    response = client.get("/")

    assert "<footer" in response.text
