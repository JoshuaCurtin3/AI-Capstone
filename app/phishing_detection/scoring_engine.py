"""The deterministic phishing risk-scoring engine.

This module (together with rules/) is the ONLY place allowed to produce the
numerical risk score. Requirements (see CLAUDE.md):

  - Deterministic: the same parsed email must always produce the same score.
    No randomness, no wall-clock/network dependence, no LLM calls.
  - Every individual rule in rules/ must be independently unit tested.
  - The Claude API (app.ai_analysis) may summarize *this* module's output in
    plain language, but must never feed back into or adjust the score.
"""

from __future__ import annotations

from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.rules import (
    attachment_analysis,
    content_analysis,
    dkim,
    dmarc,
    header_analysis,
    spf,
    url_analysis,
)
from app.phishing_detection.schemas import Finding, RiskClassification, ScoringResult

MIN_SCORE = 0
MAX_SCORE = 100

#: Checked in descending order; the first threshold the score meets or
#: exceeds wins. Matches CLAUDE.md's classification bands (0-24 Low,
#: 25-49 Medium, 50-74 High, 75-100 Critical).
_CLASSIFICATION_THRESHOLDS: tuple[tuple[int, RiskClassification], ...] = (
    (75, "Critical"),
    (50, "High"),
    (25, "Medium"),
    (0, "Low"),
)


def _classify(score: int) -> RiskClassification:
    for threshold, label in _CLASSIFICATION_THRESHOLDS:
        if score >= threshold:
            return label
    return "Low"  # pragma: no cover - unreachable, 0 is always in the table


def calculate_risk_score(parsed_email: ParsedEmail) -> ScoringResult:
    """Compute a deterministic phishing risk score for a parsed email.

    Runs every detection rule against the already-parsed email, sums their
    point contributions, and clamps the result to 0-100. A pure function of
    `parsed_email` - no network I/O, no randomness, no AI calls.
    """
    findings: list[Finding] = [
        *spf.check_spf(parsed_email),
        *dkim.check_dkim(parsed_email),
        *dmarc.check_dmarc(parsed_email),
        *dmarc.check_missing_authentication_results(parsed_email),
        *header_analysis.check_headers(parsed_email),
        *url_analysis.check_urls(parsed_email),
        *attachment_analysis.check_attachments(parsed_email),
        *content_analysis.check_content(parsed_email),
    ]

    raw_score = sum(finding.points for finding in findings)
    score = max(MIN_SCORE, min(MAX_SCORE, raw_score))

    return ScoringResult(
        score=score,
        classification=_classify(score),
        findings=findings,
        total_findings=len(findings),
    )
