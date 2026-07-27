"""Unit tests for app.phishing_detection.rules.header_analysis."""

from __future__ import annotations

from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.rules.header_analysis import (
    RECEIVED_HEADER_THRESHOLD,
    check_headers,
)


def _rule_ids(parsed: ParsedEmail) -> set[str]:
    return {f.rule_id for f in check_headers(parsed)}


# --- Reply-To mismatch ---


def test_reply_to_domain_mismatch_triggers_finding() -> None:
    parsed = ParsedEmail(from_address="Alice <alice@example.com>", reply_to="attacker@evil.example")

    assert "HDR-REPLYTO-MISMATCH" in _rule_ids(parsed)


def test_reply_to_same_domain_does_not_trigger() -> None:
    parsed = ParsedEmail(from_address="Alice <alice@example.com>", reply_to="support@example.com")

    assert "HDR-REPLYTO-MISMATCH" not in _rule_ids(parsed)


def test_reply_to_domain_comparison_is_case_insensitive() -> None:
    """Edge case: domains differing only in case are not a mismatch."""
    parsed = ParsedEmail(from_address="Alice <alice@Example.com>", reply_to="support@EXAMPLE.COM")

    assert "HDR-REPLYTO-MISMATCH" not in _rule_ids(parsed)


def test_no_reply_to_header_does_not_trigger() -> None:
    parsed = ParsedEmail(from_address="Alice <alice@example.com>", reply_to=None)

    assert "HDR-REPLYTO-MISMATCH" not in _rule_ids(parsed)


# --- Return-Path mismatch ---


def test_return_path_domain_mismatch_triggers_finding() -> None:
    parsed = ParsedEmail(
        from_address="Alice <alice@example.com>", return_path="<bounce@evil.example>"
    )

    assert "HDR-RETURNPATH-MISMATCH" in _rule_ids(parsed)


def test_return_path_same_domain_does_not_trigger() -> None:
    parsed = ParsedEmail(
        from_address="Alice <alice@example.com>", return_path="<alice@example.com>"
    )

    assert "HDR-RETURNPATH-MISMATCH" not in _rule_ids(parsed)


def test_no_return_path_header_does_not_trigger() -> None:
    parsed = ParsedEmail(from_address="Alice <alice@example.com>", return_path=None)

    assert "HDR-RETURNPATH-MISMATCH" not in _rule_ids(parsed)


# --- Suspicious display name ---


def test_display_name_with_mismatched_embedded_domain_triggers_finding() -> None:
    parsed = ParsedEmail(from_address='"security@paypal.com" <attacker@evil.example>')

    assert "HDR-SUSPICIOUS-DISPLAY-NAME" in _rule_ids(parsed)


def test_plain_display_name_does_not_trigger() -> None:
    parsed = ParsedEmail(from_address="Alice Example <alice@example.com>")

    assert "HDR-SUSPICIOUS-DISPLAY-NAME" not in _rule_ids(parsed)


def test_display_name_embedded_domain_matching_actual_domain_does_not_trigger() -> None:
    """Edge case: the display name happens to contain an address on the
    *same* domain as the real sender - not suspicious."""
    parsed = ParsedEmail(from_address='"alice@example.com" <alice@example.com>')

    assert "HDR-SUSPICIOUS-DISPLAY-NAME" not in _rule_ids(parsed)


# --- Excessive Received headers ---


def test_excessive_received_headers_triggers_finding() -> None:
    parsed = ParsedEmail(
        received_headers=[f"from hop{i}" for i in range(RECEIVED_HEADER_THRESHOLD + 1)]
    )

    assert "HDR-EXCESSIVE-RECEIVED" in _rule_ids(parsed)


def test_received_headers_at_threshold_does_not_trigger() -> None:
    """Edge case: exactly at the threshold should not trigger, only over it."""
    parsed = ParsedEmail(
        received_headers=[f"from hop{i}" for i in range(RECEIVED_HEADER_THRESHOLD)]
    )

    assert "HDR-EXCESSIVE-RECEIVED" not in _rule_ids(parsed)


def test_no_received_headers_does_not_trigger() -> None:
    parsed = ParsedEmail(received_headers=[])

    assert "HDR-EXCESSIVE-RECEIVED" not in _rule_ids(parsed)
