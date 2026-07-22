"""Database-engine-level helpers that are not tied to one domain's models.

This is the home for things like connection health checks or raw-SQL helpers
— NOT for model class definitions (those live in each domain package's
models.py) and NOT for schema migrations (see alembic/, added in Phase 5).

TODO: add a router/helper here once a concrete need exists.
"""
