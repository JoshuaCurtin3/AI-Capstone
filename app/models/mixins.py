"""Shared SQLAlchemy model mixins used across domain packages.

Domain-specific models (e.g. app/auth/models.py, app/phishing_detection/models.py)
inherit from these where relevant instead of redefining the same columns.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func


class TimeStampedMixin:
    """created_at/updated_at columns, both server-side defaults so the
    database clock (not app-server clocks, which can drift across
    processes) is the single source of truth for timestamps.
    """

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
