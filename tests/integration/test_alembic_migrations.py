"""Integration tests: `alembic upgrade head` applies cleanly to an empty
database and `alembic downgrade` reverses it (TASKS.md Phase 5's explicit
requirement) - run against a real PostgreSQL database. See
test_database.py's module docstring for why this skips itself (rather than
fails) when TEST_DATABASE_URL is unset/unreachable.

Self-contained and order-independent with respect to test_database.py/
test_dashboard.py: forces a clean slate (drops every app table plus
alembic_version) both before and after running, regardless of what those
other modules' Base.metadata.create_all/drop_all left behind.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

# Force domain models to register on Base.metadata, same as alembic/env.py.
import app.auth.models  # noqa: F401
import app.phishing_detection.models  # noqa: F401
from alembic import command
from app.database.base import Base

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

EXPECTED_TABLES = {"users", "analysis_results", "triggered_rules"}


def _clean_slate(engine: Engine) -> None:
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture
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

    _clean_slate(engine)
    yield engine
    _clean_slate(engine)
    engine.dispose()


def _alembic_config(database_url: str) -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    # Pre-setting this overrides alembic/env.py's APP_DATABASE_URL fallback
    # (see the "Only default to APP_DATABASE_URL" comment there), so
    # migrations run against the disposable test database, not production.
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def test_upgrade_head_creates_expected_tables(pg_engine: Engine) -> None:
    cfg = _alembic_config(str(pg_engine.url))

    command.upgrade(cfg, "head")

    table_names = set(inspect(pg_engine).get_table_names())
    assert EXPECTED_TABLES <= table_names


def test_downgrade_base_removes_every_app_table(pg_engine: Engine) -> None:
    cfg = _alembic_config(str(pg_engine.url))
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "base")

    table_names = set(inspect(pg_engine).get_table_names())
    assert EXPECTED_TABLES.isdisjoint(table_names)
