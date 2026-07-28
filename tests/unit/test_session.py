"""Unit tests for app.auth.session (signed session cookie handling)."""

from __future__ import annotations

from datetime import UTC, datetime
from http.cookies import SimpleCookie

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.auth.schemas import AuthenticatedUser
from app.auth.session import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    create_session_cookie,
    read_session,
)
from app.config import Settings

USER = AuthenticatedUser(
    username="alice",
    display_name="Alice Example",
    email="alice@example.local",
    groups=["CN=Required,DC=example,DC=local"],
    is_in_required_group=True,
    authenticated_at=datetime(2026, 1, 1, tzinfo=UTC),
)


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "secret_key": "test-secret-key",
        "ldap_server_uri": "ldaps://ad.example.local:636",
        "ldap_bind_dn": "CN=svc,DC=example,DC=local",
        "ldap_bind_password": "svc-pw",
        "ldap_user_search_base_dn": "OU=Users,DC=example,DC=local",
        "ldap_required_group_dn": "CN=Required,DC=example,DC=local",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _set_cookie_headers(response: Response) -> list[str]:
    return [value.decode() for key, value in response.raw_headers if key == b"set-cookie"]


def _cookie_value(response: Response, name: str) -> str:
    jar: SimpleCookie[str] = SimpleCookie()
    for header in _set_cookie_headers(response):
        jar.load(header)
    assert name in jar
    return jar[name].value


def _request_with_cookie(cookie_header: str | None) -> Request:
    headers = [(b"cookie", cookie_header.encode())] if cookie_header else []
    scope = {"type": "http", "headers": headers, "method": "GET", "path": "/", "query_string": b""}
    return Request(scope)


def test_create_and_read_session_round_trips_user() -> None:
    settings = _settings()
    response = Response()
    create_session_cookie(response, USER, settings=settings)
    token = _cookie_value(response, SESSION_COOKIE_NAME)

    request = _request_with_cookie(f"{SESSION_COOKIE_NAME}={token}")
    result = read_session(request, settings=settings)

    assert result == USER


def test_missing_cookie_returns_none() -> None:
    request = _request_with_cookie(None)

    assert read_session(request, settings=_settings()) is None


def test_tampered_cookie_is_rejected() -> None:
    settings = _settings()
    response = Response()
    create_session_cookie(response, USER, settings=settings)
    token = _cookie_value(response, SESSION_COOKIE_NAME)
    # Flip a character in the middle rather than the last character - the
    # last base64 character can have padding-irrelevant bits, so tampering
    # with it can silently decode to the same byte and not actually change
    # the signature.
    middle = len(token) // 2
    replacement = "a" if token[middle] != "a" else "b"
    tampered = token[:middle] + replacement + token[middle + 1 :]

    request = _request_with_cookie(f"{SESSION_COOKIE_NAME}={tampered}")

    assert read_session(request, settings=settings) is None


def test_expired_cookie_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    response = Response()
    # Sign the cookie as if it were created at the Unix epoch, so a normal
    # read (real current time, default max_age) sees it as ~decades old -
    # deterministic without sleeping or relying on sub-second timing.
    with monkeypatch.context() as patched_time:
        patched_time.setattr("itsdangerous.timed.TimestampSigner.get_timestamp", lambda self: 0)
        create_session_cookie(response, USER, settings=settings)
    token = _cookie_value(response, SESSION_COOKIE_NAME)
    request = _request_with_cookie(f"{SESSION_COOKIE_NAME}={token}")

    assert read_session(request, settings=settings) is None


def test_session_cookie_is_httponly_and_samesite_lax() -> None:
    response = Response()
    create_session_cookie(response, USER, settings=_settings())

    (header,) = _set_cookie_headers(response)
    assert "HttpOnly" in header
    assert "samesite=lax" in header.lower()


def test_session_cookie_is_secure_in_production_but_not_development() -> None:
    dev_response = Response()
    create_session_cookie(dev_response, USER, settings=_settings(environment="development"))
    (dev_header,) = _set_cookie_headers(dev_response)
    assert "Secure" not in dev_header

    prod_response = Response()
    create_session_cookie(prod_response, USER, settings=_settings(environment="production"))
    (prod_header,) = _set_cookie_headers(prod_response)
    assert "Secure" in prod_header


def test_clear_session_cookie_expires_it() -> None:
    response = Response()
    clear_session_cookie(response)

    (header,) = _set_cookie_headers(response)
    assert header.startswith(f"{SESSION_COOKIE_NAME}=")
    assert "1970" in header or "Max-Age=0" in header
