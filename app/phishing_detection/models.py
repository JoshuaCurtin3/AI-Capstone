"""SQLAlchemy models for persisted scoring results.

AnalysisResult/TriggeredRule persist exactly what
app.phishing_detection.schemas.ScoringResult/Finding already produced - this
module never computes a score itself, only stores one that's already been
computed (see CLAUDE.md: the score is produced exclusively by
scoring_engine.calculate_risk_score). See services.py for the write path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimeStampedMixin

if TYPE_CHECKING:
    from app.auth.models import User


class AnalysisResult(TimeStampedMixin, Base):
    """One /upload submission's outcome. `submitted_by_id` is nullable
    because /upload is intentionally still public (see TASKS.md Phase 6) -
    an anonymous, unauthenticated visitor can submit an email for analysis,
    and that analysis is still recorded, just with no attributable user.
    """

    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    submitted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: RFC 5322 recommends header lines stay under 998 characters; generous
    #: enough for any real Subject/From without being unbounded.
    subject: Mapped[str | None] = mapped_column(String(998), nullable=True)
    from_address: Mapped[str | None] = mapped_column(String(998), nullable=True)
    score: Mapped[int] = mapped_column()
    classification: Mapped[str] = mapped_column(String(16))
    total_findings: Mapped[int] = mapped_column()

    submitted_by: Mapped[User | None] = relationship(back_populates="analysis_results")
    triggered_rules: Mapped[list[TriggeredRule]] = relationship(
        back_populates="analysis_result",
        cascade="all, delete-orphan",
        order_by="TriggeredRule.id",
    )


class TriggeredRule(Base):
    """One triggered Finding from a ScoringResult, persisted verbatim."""

    __tablename__ = "triggered_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_result_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_results.id", ondelete="CASCADE")
    )
    rule_id: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    points: Mapped[int] = mapped_column()
    evidence: Mapped[str] = mapped_column(Text())
    explanation: Mapped[str] = mapped_column(Text())

    analysis_result: Mapped[AnalysisResult] = relationship(back_populates="triggered_rules")
