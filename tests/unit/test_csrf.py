"""Unit tests for app.core.security (double-submit-cookie CSRF protection)."""

from __future__ import annotations

from starlette.requests import Request

from app.core.security import generate_csrf_token, verify_csrf_token


def _request_with_cookie(cookie_header: str | None) -> Request:
    headers = [(b"cookie", cookie_header.encode())] if cookie_header else []
    scope = {
        "type": "http",
        "headers": headers,
        "method": "POST",
        "path": "/login",
        "query_string": b"",
    }
    return Request(scope)


def test_matching_cookie_and_submitted_token_passes() -> None:
    token = generate_csrf_token()
    request = _request_with_cookie(f"csrf_token={token}")

    assert verify_csrf_token(request, token) is True


def test_missing_cookie_fails() -> None:
    request = _request_with_cookie(None)

    assert verify_csrf_token(request, "some-token") is False


def test_missing_submitted_token_fails() -> None:
    token = generate_csrf_token()
    request = _request_with_cookie(f"csrf_token={token}")

    assert verify_csrf_token(request, None) is False


def test_mismatched_token_fails() -> None:
    token = generate_csrf_token()
    request = _request_with_cookie(f"csrf_token={token}")

    assert verify_csrf_token(request, "a-completely-different-token") is False


def test_generated_tokens_are_unique() -> None:
    assert generate_csrf_token() != generate_csrf_token()
