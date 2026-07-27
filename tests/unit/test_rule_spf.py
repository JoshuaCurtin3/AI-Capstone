"""Unit tests for app.phishing_detection.rules.spf.check_spf."""

from __future__ import annotations

from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.rules.spf import check_spf


def test_spf_fail_triggers_finding() -> None:
    parsed = ParsedEmail(
        authentication_results=["mx.example.com; spf=fail smtp.mailfrom=evil.example"]
    )

    findings = check_spf(parsed)

    assert len(findings) == 1
    assert findings[0].rule_id == "AUTH-SPF-FAIL"
    assert findings[0].points == 15
    assert "spf=fail" in findings[0].evidence


def test_spf_pass_does_not_trigger() -> None:
    parsed = ParsedEmail(
        authentication_results=["mx.example.com; spf=pass smtp.mailfrom=example.com"]
    )

    assert check_spf(parsed) == []


def test_no_authentication_results_header_does_not_trigger_spf_rule() -> None:
    """Edge case: an absent header is its own separate rule (AUTH-MISSING-RESULTS
    in dmarc.py) - the spf rule itself must not fire on missing data."""
    parsed = ParsedEmail(authentication_results=[])

    assert check_spf(parsed) == []


def test_spf_softfail_does_not_trigger() -> None:
    """Edge case: only an exact "fail" verdict counts - softfail/neutral are
    weaker signals intentionally left unscored by this rule."""
    parsed = ParsedEmail(
        authentication_results=["mx.example.com; spf=softfail smtp.mailfrom=example.com"]
    )

    assert check_spf(parsed) == []


def test_first_authentication_results_header_wins() -> None:
    """Edge case: multiple Authentication-Results headers (multi-hop) - only
    the first (closest, most trustworthy) entry is consulted."""
    parsed = ParsedEmail(
        authentication_results=[
            "mx.example.com; spf=pass smtp.mailfrom=example.com",
            "relay.example.net; spf=fail smtp.mailfrom=evil.example",
        ]
    )

    assert check_spf(parsed) == []
