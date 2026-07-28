"""Alembic environment - wires migrations to the app's own SQLAlchemy
metadata and typed settings.

The database URL is never read from alembic.ini (which is committed to
source control) - it's read from APP_DATABASE_URL via app.config.get_settings(),
the same env-var-only source the application itself uses, per CLAUDE.md's
"no secrets in source control" rule.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Force every domain package's models module to import, so its tables
# register on Base.metadata before target_metadata is read below. New
# domain models must be added here to be picked up by `alembic revision
# --autogenerate` and by the migration-completeness check in
# tests/integration/test_alembic_migrations.py.
import app.auth.models  # noqa: F401,E402
import app.phishing_detection.models  # noqa: F401,E402
from alembic import context
from app.config import get_settings  # noqa: E402
from app.database.base import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Only default to APP_DATABASE_URL if the caller hasn't already set a URL -
# lets tests/integration/test_alembic_migrations.py point migrations at a
# separate TEST_DATABASE_URL via the Alembic Python API
# (Config.set_main_option) without this overriding it back to production
# settings; normal `alembic upgrade head` CLI usage has nothing pre-set, so
# it always falls back to APP_DATABASE_URL as before.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (`alembic upgrade
    head --sql`); not used in normal deploys, kept for completeness.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection - the normal path."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
