"""End-to-end auth flow tests: login form -> LDAP auth (mocked) -> session
cookie -> protected route -> logout. Exercises app.auth.router,
app.auth.middleware, app.auth.session, and app.core.security together
through a real FastAPI TestClient, the same way a browser would.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.auth import ldap_backend
from app.auth.schemas import AuthenticatedUser
from app.main import app

AUTHORIZED_USER = AuthenticatedUser(
    username="alice",
    display_name="Alice Example",
    email="alice@example.local",
    groups=["CN=Required,DC=example,DC=local"],
    is_in_required_group=True,
    authenticated_at=datetime(2026, 1, 1, tzinfo=UTC),
)

UNAUTHORIZED_USER = AuthenticatedUser(
    username="bob",
    display_name="Bob NoAccess",
    email=None,
    groups=[],
    is_in_required_group=False,
    authenticated_at=datetime(2026, 1, 1, tzinfo=UTC),
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _csrf_token(client: TestClient) -> str:
    response = client.get("/login")
    assert response.status_code == 200
    token = client.cookies.get("csrf_token")
    assert token
    return token


def test_login_page_renders_csrf_and_next_field(client: TestClient) -> None:
    response = client.get("/login?next=/account")

    assert response.status_code == 200
    assert 'name="csrf_token"' in response.text
    assert 'value="/account"' in response.text


def test_login_success_sets_session_cookie_and_redirects_to_next(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ldap_backend, "authenticate", lambda u, p: AUTHORIZED_USER)
    csrf_token = _csrf_token(client)

    response = client.post(
        "/login",
        data={
            "username": "alice",
            "password": "correct",
            "csrf_token": csrf_token,
            "next": "/account",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/account"
    assert "session" in response.cookies


def test_login_success_defaults_to_root_when_no_next(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ldap_backend, "authenticate", lambda u, p: AUTHORIZED_USER)
    csrf_token = _csrf_token(client)

    response = client.post(
        "/login",
        data={"username": "alice", "password": "correct", "csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_login_rejects_open_redirect_next_and_falls_back_to_root(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ldap_backend, "authenticate", lambda u, p: AUTHORIZED_USER)
    csrf_token = _csrf_token(client)

    response = client.post(
        "/login",
        data={
            "username": "alice",
            "password": "correct",
            "csrf_token": csrf_token,
            "next": "https://evil.example/phish",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_login_wrong_credentials_returns_generic_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ldap_backend, "authenticate", lambda u, p: None)
    csrf_token = _csrf_token(client)

    response = client.post(
        "/login",
        data={"username": "alice", "password": "wrong", "csrf_token": csrf_token},
    )

    assert response.status_code == 401
    assert "Invalid username or password." in response.text
    assert "session" not in response.cookies


def test_login_unauthorized_group_returns_distinct_403(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ldap_backend, "authenticate", lambda u, p: UNAUTHORIZED_USER)
    csrf_token = _csrf_token(client)

    response = client.post(
        "/login",
        data={"username": "bob", "password": "correct", "csrf_token": csrf_token},
    )

    assert response.status_code == 403
    assert "not authorized to use this application" in response.text
    assert "session" not in response.cookies


def test_login_missing_csrf_cookie_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ldap_backend, "authenticate", lambda u, p: AUTHORIZED_USER)
    # Never visited /login, so no csrf_token cookie exists yet in this client.
    response = client.post(
        "/login",
        data={"username": "alice", "password": "correct", "csrf_token": "made-up-token"},
    )

    assert response.status_code == 403
    assert "Invalid or expired form submission" in response.text


def test_login_mismatched_csrf_token_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ldap_backend, "authenticate", lambda u, p: AUTHORIZED_USER)
    _csrf_token(client)  # establishes the real cookie, which we then ignore

    response = client.post(
        "/login",
        data={"username": "alice", "password": "correct", "csrf_token": "not-the-real-token"},
    )

    assert response.status_code == 403


def test_protected_route_without_session_redirects_to_login_preserving_next(
    client: TestClient,
) -> None:
    response = client.get("/account", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=/account"


def test_protected_route_with_valid_session_returns_200(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ldap_backend, "authenticate", lambda u, p: AUTHORIZED_USER)
    csrf_token = _csrf_token(client)
    client.post(
        "/login",
        data={"username": "alice", "password": "correct", "csrf_token": csrf_token},
    )

    response = client.get("/account")

    assert response.status_code == 200
    assert "Alice Example" in response.text
    assert "alice@example.local" in response.text


def test_already_authenticated_user_visiting_login_is_redirected_away(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ldap_backend, "authenticate", lambda u, p: AUTHORIZED_USER)
    csrf_token = _csrf_token(client)
    client.post(
        "/login",
        data={"username": "alice", "password": "correct", "csrf_token": csrf_token},
    )

    response = client.get("/login", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_logout_clears_session_and_redirects_home(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ldap_backend, "authenticate", lambda u, p: AUTHORIZED_USER)
    csrf_token = _csrf_token(client)
    client.post(
        "/login", data={"username": "alice", "password": "correct", "csrf_token": csrf_token}
    )
    assert client.get("/account").status_code == 200

    response = client.post("/logout", data={"csrf_token": csrf_token}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    # The session cookie itself must be cleared, not just the account page's
    # access - a follow-up request to the protected route must bounce again.
    assert client.get("/account", follow_redirects=False).status_code == 303


def test_logout_without_valid_csrf_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ldap_backend, "authenticate", lambda u, p: AUTHORIZED_USER)
    csrf_token = _csrf_token(client)
    client.post(
        "/login", data={"username": "alice", "password": "correct", "csrf_token": csrf_token}
    )

    response = client.post("/logout", data={"csrf_token": "wrong-token"})

    assert response.status_code == 403
    # Still logged in - logout must not have taken effect.
    assert client.get("/account").status_code == 200
