"""Persistence for already-computed scoring results.

This module only ever *stores* a ScoringResult - it must never compute or
adjust a score itself (see CLAUDE.md's core rule: scoring lives exclusively
in scoring_engine.calculate_risk_score). Called from app/api/v1/upload.py
right after calculate_risk_score() runs.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth.models import User
from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.models import AnalysisResult, TriggeredRule
from app.phishing_detection.schemas import ScoringResult


def save_analysis_result(
    db: Session,
    *,
    parsed: ParsedEmail,
    scoring: ScoringResult,
    submitted_by: User | None,
) -> AnalysisResult:
    """Persist `scoring` (plus enough of `parsed` to identify the email
    later) as a new AnalysisResult row, one TriggeredRule row per finding.

    Does not commit - callers control the transaction boundary.
    """
    result = AnalysisResult(
        submitted_by=submitted_by,
        subject=parsed.subject,
        from_address=parsed.from_address,
        score=scoring.score,
        classification=scoring.classification,
        total_findings=scoring.total_findings,
        triggered_rules=[
            TriggeredRule(
                rule_id=finding.rule_id,
                category=finding.category,
                name=finding.name,
                points=finding.points,
                evidence=finding.evidence,
                explanation=finding.explanation,
            )
            for finding in scoring.findings
        ],
    )
    db.add(result)
    db.flush()
    return result
