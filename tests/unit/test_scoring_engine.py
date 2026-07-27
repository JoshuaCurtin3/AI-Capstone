"""Integration tests for app.phishing_detection.scoring_engine.calculate_risk_score.

These verify rule outputs are combined deterministically into a single
score/classification - individual rule behavior is covered by the
tests/unit/test_rule_*.py modules.
"""

from __future__ import annotations

from pathlib import Path

from app.email_parser.parser import parse_email
from app.email_parser.schemas import AttachmentMeta, ParsedEmail, ParsedURL
from app.phishing_detection.scoring_engine import _classify, calculate_risk_score

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_clean_email_scores_zero_and_classifies_low() -> None:
    """A "clean" email needs a passing Authentication-Results header -
    ParsedEmail() with no header at all legitimately triggers
    AUTH-MISSING-RESULTS on its own (see test_missing_authentication_results
    below), so it isn't the right fixture for a genuine zero-findings case.
    """
    parsed = ParsedEmail(
        from_address="Alice <alice@example.com>",
        authentication_results=["mx.example.com; spf=pass dkim=pass dmarc=pass"],
    )

    result = calculate_risk_score(parsed)

    assert result.score == 0
    assert result.classification == "Low"
    assert result.findings == []
    assert result.total_findings == 0


def test_missing_authentication_results_header_alone_scores_low_risk() -> None:
    result = calculate_risk_score(ParsedEmail())

    assert result.score == 10
    assert result.classification == "Low"
    assert result.total_findings == 1
    assert result.findings[0].rule_id == "AUTH-MISSING-RESULTS"


def test_score_is_deterministic_for_identical_input() -> None:
    parsed = ParsedEmail(authentication_results=["mx.example.com; spf=fail dkim=fail dmarc=fail"])

    first = calculate_risk_score(parsed)
    second = calculate_risk_score(parsed)

    assert first == second


def test_score_sums_points_from_multiple_categories() -> None:
    parsed = ParsedEmail(
        authentication_results=["mx.example.com; spf=fail dkim=pass dmarc=pass"],
        # https:// so this contributes only URL-IP-ADDRESS, not also
        # URL-INSECURE-HTTP - keeps this test isolated to two findings.
        urls=[ParsedURL(url="https://192.168.1.1/login", source="text")],
    )

    result = calculate_risk_score(parsed)

    assert result.score == 15 + 20  # AUTH-SPF-FAIL + URL-IP-ADDRESS
    assert result.total_findings == 2
    assert {f.rule_id for f in result.findings} == {"AUTH-SPF-FAIL", "URL-IP-ADDRESS"}


def test_score_is_capped_at_100() -> None:
    """Edge case: enough triggered findings to exceed 100 raw points must
    still clamp to the documented 0-100 range."""
    parsed = ParsedEmail(
        authentication_results=[],  # missing-results: +10
        from_address="Alice <alice@example.com>",
        reply_to="attacker@evil.example",  # reply-to mismatch: +10
        return_path="<bounce@another-evil.example>",  # return-path mismatch: +10
        urls=[
            ParsedURL(url="http://192.168.1.1/login", source="text"),  # ip: +20, http: +5
            ParsedURL(url="https://xn--pypal-4ve.com/login", source="text"),  # punycode: +15
            ParsedURL(url="https://bit.ly/x", source="text"),  # shortener: +10
            ParsedURL(url="https://free.xyz/x", source="text"),  # suspicious tld: +10
        ],
        attachments=[
            AttachmentMeta(
                filename="invoice.pdf.exe",
                content_type="application/octet-stream",
                size_bytes=1,
                sha256="0" * 64,
            )
        ],
        text_body="Urgent: reset your password immediately, payment is overdue.",
    )

    result = calculate_risk_score(parsed)

    assert result.score == 100
    raw_total = sum(f.points for f in result.findings)
    assert raw_total > 100


def test_score_never_goes_below_zero() -> None:
    """No rule currently produces negative points, but the clamp itself
    must not break on the empty/zero-finding case."""
    result = calculate_risk_score(ParsedEmail())

    assert result.score >= 0


def test_classification_boundaries() -> None:
    boundary_cases = [
        (0, "Low"),
        (24, "Low"),
        (25, "Medium"),
        (49, "Medium"),
        (50, "High"),
        (74, "High"),
        (75, "Critical"),
        (100, "Critical"),
    ]

    for score, expected in boundary_cases:
        assert _classify(score) == expected


def test_legitimate_fixture_scores_zero() -> None:
    parsed = parse_email(_load("legitimate.eml"))

    result = calculate_risk_score(parsed)

    assert result.score == 0
    assert result.classification == "Low"
    assert result.findings == []


def test_phishing_fixture_triggers_multiple_high_risk_findings() -> None:
    parsed = parse_email(_load("phishing.eml"))

    result = calculate_risk_score(parsed)

    triggered_rule_ids = {f.rule_id for f in result.findings}
    assert "AUTH-SPF-FAIL" in triggered_rule_ids
    assert "AUTH-DKIM-FAIL" in triggered_rule_ids
    assert "HDR-REPLYTO-MISMATCH" in triggered_rule_ids
    assert "HDR-RETURNPATH-MISMATCH" in triggered_rule_ids
    assert "URL-DISPLAY-MISMATCH" in triggered_rule_ids
    assert "ATT-EXECUTABLE" in triggered_rule_ids
    assert "ATT-DOUBLE-EXTENSION" in triggered_rule_ids
    assert "CONTENT-URGENCY" in triggered_rule_ids
    assert result.total_findings == len(result.findings)
    assert result.score >= 50
    assert result.classification in {"High", "Critical"}
