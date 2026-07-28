"""SQLAlchemy engine/session factory and the FastAPI `get_db` dependency.

`create_engine()` is lazy - it never opens a real connection until the
first query - so importing this module (e.g. transitively via app.main) is
always safe even when APP_DATABASE_URL points at an unreachable database;
the failure only surfaces at the first actual query, which callers handle
explicitly (see app/api/v1/upload.py and app/auth/router.py's best-effort
persistence).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

#: pool_pre_ping issues a cheap "is this connection still alive" check
#: before handing a pooled connection out, so a DB restart/network blip
#: doesn't surface as an opaque broken-connection error on the next request.
#: connect_timeout bounds how long a *new* connection attempt can take -
#: see Settings.database_connect_timeout_seconds's docstring for why this
#: matters even though persistence is already best-effort.
_settings = get_settings()
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": _settings.database_connect_timeout_seconds},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a request-scoped Session, always closed
    after. Callers are responsible for calling `db.commit()` themselves -
    this dependency does not auto-commit, so a route that reads but never
    writes doesn't need to think about transactions at all.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
