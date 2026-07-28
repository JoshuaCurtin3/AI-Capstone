"""Integration tests for the Phase 5 SQLAlchemy models and services, run
against a real PostgreSQL database (never SQLite, to match production - see
TASKS.md Phase 5).

Requires TEST_DATABASE_URL to point at a reachable, disposable PostgreSQL
database. If it's unset or unreachable, every test in this module is
skipped (not failed) - see the `pg_engine` fixture. This keeps `pytest`
green in environments with no Postgres available (e.g. this sandbox) while
still providing real coverage wherever a test database exists (CI once
Phase 9 adds a Postgres service container, or a developer machine/the
Ubuntu VM with TEST_DATABASE_URL set).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.schemas import AuthenticatedUser
from app.auth.services import get_or_create_user
from app.database.base import Base
from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.models import AnalysisResult, TriggeredRule
from app.phishing_detection.schemas import Finding, ScoringResult
from app.phishing_detection.services import save_analysis_result


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
    """A Session bound to a single connection/transaction that's rolled
    back after each test, so tests never leave permanent data even against
    a shared test database.
    """
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _authenticated_user(username: str = "alice", **overrides: object) -> AuthenticatedUser:
    defaults: dict[str, object] = {
        "username": username,
        "display_name": "Alice Example",
        "email": "alice@example.local",
        "groups": ["CN=Required,DC=example,DC=local"],
        "is_in_required_group": True,
        "authenticated_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return AuthenticatedUser(**defaults)  # type: ignore[arg-type]


def _scoring_result() -> ScoringResult:
    findings = [
        Finding(
            rule_id="AUTH-SPF-FAIL",
            category="authentication",
            name="SPF failed",
            points=15,
            evidence="spf=fail",
            explanation="The sending server failed SPF authentication.",
        ),
        Finding(
            rule_id="URL-IP-ADDRESS",
            category="url",
            name="URL uses an IP address",
            points=20,
            evidence="http://192.168.1.1/login",
            explanation="Legitimate companies rarely link directly to a bare IP.",
        ),
    ]
    return ScoringResult(score=35, classification="Medium", findings=findings, total_findings=2)


def test_user_round_trips(db: Session) -> None:
    user = User(username="alice", display_name="Alice Example", email="alice@example.local")
    db.add(user)
    db.flush()

    fetched = db.execute(select(User).where(User.username == "alice")).scalar_one()

    assert fetched.display_name == "Alice Example"
    assert fetched.email == "alice@example.local"
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


def test_user_username_is_unique(db: Session) -> None:
    db.add(User(username="alice", display_name="Alice Example"))
    db.flush()
    db.add(User(username="alice", display_name="A Different Alice"))

    with pytest.raises(IntegrityError):
        db.flush()


def test_get_or_create_user_upserts_by_username(db: Session) -> None:
    first = get_or_create_user(db, _authenticated_user(display_name="Alice V1"))
    db.flush()
    first_id = first.id

    second = get_or_create_user(db, _authenticated_user(display_name="Alice V2"))
    db.flush()

    assert second.id == first_id  # same row, not a duplicate
    assert second.display_name == "Alice V2"
    assert db.execute(select(User)).scalars().all() == [second]


def test_analysis_result_round_trips_with_triggered_rules(db: Session) -> None:
    user = User(username="alice", display_name="Alice Example")
    db.add(user)
    db.flush()

    result = save_analysis_result(
        db,
        parsed=ParsedEmail(subject="Urgent: verify now", from_address="attacker@evil.example"),
        scoring=_scoring_result(),
        submitted_by=user,
    )
    db.flush()

    fetched = db.execute(select(AnalysisResult).where(AnalysisResult.id == result.id)).scalar_one()
    assert fetched.subject == "Urgent: verify now"
    assert fetched.from_address == "attacker@evil.example"
    assert fetched.score == 35
    assert fetched.classification == "Medium"
    assert fetched.total_findings == 2
    assert fetched.submitted_by_id == user.id
    assert len(fetched.triggered_rules) == 2
    assert {rule.rule_id for rule in fetched.triggered_rules} == {"AUTH-SPF-FAIL", "URL-IP-ADDRESS"}


def test_analysis_result_submitted_by_is_nullable_for_anonymous_upload(db: Session) -> None:
    """/upload is intentionally public (Phase 6) - an anonymous submission
    must still persist, just with no attributable user.
    """
    result = save_analysis_result(
        db,
        parsed=ParsedEmail(subject="Anonymous submission"),
        scoring=_scoring_result(),
        submitted_by=None,
    )
    db.flush()

    fetched = db.execute(select(AnalysisResult).where(AnalysisResult.id == result.id)).scalar_one()
    assert fetched.submitted_by_id is None


def test_deleting_analysis_result_cascades_to_triggered_rules(db: Session) -> None:
    result = save_analysis_result(
        db, parsed=ParsedEmail(), scoring=_scoring_result(), submitted_by=None
    )
    db.flush()
    result_id = result.id

    db.delete(result)
    db.flush()

    assert (
        db.execute(
            select(TriggeredRule).where(TriggeredRule.analysis_result_id == result_id)
        ).first()
        is None
    )
