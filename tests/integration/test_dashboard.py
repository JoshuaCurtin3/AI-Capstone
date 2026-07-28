"""Integration tests for GET /dashboard, run against a real PostgreSQL
database - see test_database.py's module docstring for why these skip
themselves (rather than fail) when TEST_DATABASE_URL is unset/unreachable.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth import ldap_backend
from app.auth.models import User
from app.auth.schemas import AuthenticatedUser
from app.database.base import Base
from app.database.session import get_db
from app.email_parser.schemas import ParsedEmail
from app.main import app
from app.phishing_detection.schemas import Finding, ScoringResult
from app.phishing_detection.services import save_analysis_result

ALICE = AuthenticatedUser(
    username="alice",
    display_name="Alice Example",
    email="alice@example.local",
    groups=["CN=Required,DC=example,DC=local"],
    is_in_required_group=True,
    authenticated_at=datetime(2026, 1, 1, tzinfo=UTC),
)

BOB = AuthenticatedUser(
    username="bob",
    display_name="Bob Example",
    email="bob@example.local",
    groups=["CN=Required,DC=example,DC=local"],
    is_in_required_group=True,
    authenticated_at=datetime(2026, 1, 1, tzinfo=UTC),
)


@pytest.fixture(scope="module")
def pg_engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set - skipping Postgres integration tests")

    engine = create_engine(url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect():
            pass
    except OperationalError as exc:
        engine.dispose()
        pytest.skip(f"Cannot reach TEST_DATABASE_URL: {exc}")

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(pg_engine: Engine) -> Iterator[Session]:
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _login(client: TestClient, monkeypatch: pytest.MonkeyPatch, user: AuthenticatedUser) -> None:
    monkeypatch.setattr(ldap_backend, "authenticate", lambda u, p: user)
    login_page = client.get("/login")
    assert login_page.status_code == 200
    csrf_token = client.cookies.get("csrf_token")
    assert csrf_token
    response = client.post(
        "/login", data={"username": user.username, "password": "x", "csrf_token": csrf_token}
    )
    assert response.status_code in (200, 303)


def _seed_result(db: Session, *, submitted_by: User | None, subject: str) -> None:
    scoring = ScoringResult(
        score=10,
        classification="Low",
        findings=[
            Finding(
                rule_id="CONTENT-URGENCY",
                category="content",
                name="Urgency language",
                points=5,
                evidence="urgent",
                explanation="Uses urgency language.",
            )
        ],
        total_findings=1,
    )
    save_analysis_result(
        db, parsed=ParsedEmail(subject=subject), scoring=scoring, submitted_by=submitted_by
    )
    db.flush()


def test_dashboard_requires_login(client: TestClient) -> None:
    response = client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=/dashboard"


def test_dashboard_shows_only_current_users_results(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    _login(client, monkeypatch, ALICE)

    alice_row = db.query(User).filter_by(username="alice").one()
    bob_row = User(username="bob", display_name="Bob Example", email="bob@example.local")
    db.add(bob_row)
    db.flush()

    _seed_result(db, submitted_by=alice_row, subject="Alice's analysis")
    _seed_result(db, submitted_by=bob_row, subject="Bob's analysis")
    _seed_result(db, submitted_by=None, subject="Anonymous analysis")

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Alice&#39;s analysis" in response.text or "Alice's analysis" in response.text
    assert "Bob&#39;s analysis" not in response.text and "Bob's analysis" not in response.text
    assert "Anonymous analysis" not in response.text


def test_dashboard_shows_empty_state_with_no_results(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(client, monkeypatch, ALICE)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "No analyses yet" in response.text
