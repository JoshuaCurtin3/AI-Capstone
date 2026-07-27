"""Typed structures for the scoring engine's input and output.

Independent of SQLAlchemy - `ScoringResult` is the contract between
`scoring_engine.calculate_risk_score` and every downstream consumer (the
upload results page, and eventually app.ai_analysis, which may only read a
finished ScoringResult, never influence it - see CLAUDE.md).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

RiskClassification = Literal["Low", "Medium", "High", "Critical"]

RuleCategory = Literal["authentication", "header", "url", "attachment", "content"]


class Finding(BaseModel):
    """One triggered detection rule.

    `explanation` is a fixed, rule-authored sentence describing why this
    rule exists in general - not AI-generated prose about this specific
    email. Per CLAUDE.md/TASKS.md Phase 4, only Phase 7's Claude API call
    may generate free-form explanatory text about a specific analysis
    result; this stays a static template so the scoring path has zero LLM
    involvement.
    """

    rule_id: str
    category: RuleCategory
    name: str
    points: int
    evidence: str
    explanation: str


class ScoringResult(BaseModel):
    """Deterministic output of app.phishing_detection.scoring_engine."""

    score: int
    classification: RiskClassification
    findings: list[Finding]
    total_findings: int
