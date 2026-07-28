"""Database-engine-level helpers that are not tied to one domain's models.

This is the home for things like connection health checks or raw-SQL helpers
- NOT for model class definitions (those live in each domain package's
models.py, per docs/architecture.md's "domain-specific code lives in its
domain package" rule) and NOT for schema migrations (see alembic/).
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base every domain package's models.py inherits from.

    Kept empty on purpose - a single shared metadata registry is the only
    thing that needs to be common across domains, so alembic/env.py can
    discover every model's table via `Base.metadata`.
    """
