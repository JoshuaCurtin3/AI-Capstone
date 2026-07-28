"""SQLAlchemy model for a locally-cached AD user record.

This table never stores a password or any AD credential - per CLAUDE.md's
"no local password auth" / "no parallel local-auth path" rule, Active
Directory over LDAPS remains the sole source of truth for identity and
authorization on *every* login (see app/auth/ldap_backend.py). This row
exists only so app.phishing_detection's AnalysisResult can reference *who*
ran an analysis, and so /dashboard can show a per-user history. It's
upserted from the already-authenticated AuthenticatedUser's fields at
successful login time (app/auth/services.py::get_or_create_user).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimeStampedMixin

if TYPE_CHECKING:
    from app.phishing_detection.models import AnalysisResult


class User(TimeStampedMixin, Base):
    """A local reference to an AD identity - display data only, never a
    credential. `updated_at` (from TimeStampedMixin) doubles as a "last
    seen" timestamp, since this row is only ever touched on login.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: AD's sAMAccountName (or configured login attribute) - stable and
    #: unique per directory, unlike display_name/email which can change.
    username: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(256))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    analysis_results: Mapped[list[AnalysisResult]] = relationship(back_populates="submitted_by")
