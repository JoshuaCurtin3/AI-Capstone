"""Unit tests for app.phishing_detection.rules.dkim.check_dkim."""

from __future__ import annotations

from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.rules.dkim import check_dkim


def test_dkim_fail_triggers_finding() -> None:
    parsed = ParsedEmail(
        authentication_results=["mx.example.com; dkim=fail header.i=@evil.example"]
    )

    findings = check_dkim(parsed)

    assert len(findings) == 1
    assert findings[0].rule_id == "AUTH-DKIM-FAIL"
    assert findings[0].points == 15
    assert "dkim=fail" in findings[0].evidence


def test_dkim_pass_does_not_trigger() -> None:
    parsed = ParsedEmail(authentication_results=["mx.example.com; dkim=pass header.d=example.com"])

    assert check_dkim(parsed) == []


def test_dkim_none_does_not_trigger() -> None:
    """Edge case: an unsigned message (dkim=none) is not the same as a
    failed signature check - only "fail" is scored by this rule."""
    parsed = ParsedEmail(authentication_results=["mx.example.com; dkim=none"])

    assert check_dkim(parsed) == []


def test_no_authentication_results_does_not_trigger_dkim_rule() -> None:
    parsed = ParsedEmail(authentication_results=[])

    assert check_dkim(parsed) == []
