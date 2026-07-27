"""Unit tests for app.phishing_detection.rules.dmarc: check_dmarc and
check_missing_authentication_results.
"""

from __future__ import annotations

from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.rules.dmarc import (
    check_dmarc,
    check_missing_authentication_results,
)


def test_dmarc_fail_triggers_finding() -> None:
    parsed = ParsedEmail(
        authentication_results=["mx.example.com; dmarc=fail header.from=evil.example"]
    )

    findings = check_dmarc(parsed)

    assert len(findings) == 1
    assert findings[0].rule_id == "AUTH-DMARC-FAIL"
    assert findings[0].points == 15
    assert "dmarc=fail" in findings[0].evidence


def test_dmarc_pass_does_not_trigger() -> None:
    parsed = ParsedEmail(
        authentication_results=["mx.example.com; dmarc=pass header.from=example.com"]
    )

    assert check_dmarc(parsed) == []


def test_dmarc_missing_from_header_does_not_trigger_fail_rule() -> None:
    """Edge case: a header present but with no dmarc= mechanism at all
    (e.g. an SPF/DKIM-only Authentication-Results value) must not be
    treated as a failure."""
    parsed = ParsedEmail(
        authentication_results=["mx.example.com; spf=pass smtp.mailfrom=example.com"]
    )

    assert check_dmarc(parsed) == []


def test_missing_authentication_results_header_triggers_finding() -> None:
    parsed = ParsedEmail(authentication_results=[])

    findings = check_missing_authentication_results(parsed)

    assert len(findings) == 1
    assert findings[0].rule_id == "AUTH-MISSING-RESULTS"
    assert findings[0].points == 10


def test_present_authentication_results_header_does_not_trigger_missing_rule() -> None:
    parsed = ParsedEmail(authentication_results=["mx.example.com; spf=pass"])

    assert check_missing_authentication_results(parsed) == []
