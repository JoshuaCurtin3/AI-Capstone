"""Shared SQLAlchemy model mixins used across domain packages.

Domain-specific models (e.g. app/email_parser/models.py) should inherit from
these where relevant instead of redefining the same columns.

TODO(Phase 5): implement using SQLAlchemy's declarative mixin pattern, e.g.:

    from datetime import datetime
    from sqlalchemy.orm import Mapped, mapped_column
    from sqlalchemy.sql import func

    class TimeStampedMixin:
        created_at: Mapped[datetime] = mapped_column(server_default=func.now())
        updated_at: Mapped[datetime] = mapped_column(
            server_default=func.now(), onupdate=func.now()
        )

Left unimplemented until Phase 5 introduces the SQLAlchemy declarative base
(app/database/base.py) this would attach to.
"""
