"""Unit tests for app.phishing_detection.rules.content_analysis."""

from __future__ import annotations

from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.rules.content_analysis import check_content


def _rule_ids(parsed: ParsedEmail) -> set[str]:
    return {f.rule_id for f in check_content(parsed)}


# --- Urgency language ---


def test_urgency_phrase_triggers_finding() -> None:
    parsed = ParsedEmail(subject="Urgent: action required on your account")

    assert "CONTENT-URGENCY" in _rule_ids(parsed)


def test_neutral_subject_does_not_trigger_urgency_rule() -> None:
    parsed = ParsedEmail(subject="Quarterly report attached")

    assert "CONTENT-URGENCY" not in _rule_ids(parsed)


def test_urgency_phrase_match_is_case_insensitive() -> None:
    """Edge case: phrase matching must not depend on the original casing."""
    parsed = ParsedEmail(text_body="Please act NOW before your access is revoked.")

    assert "CONTENT-URGENCY" in _rule_ids(parsed)


# --- Credential harvesting language ---


def test_credential_harvesting_phrase_triggers_finding() -> None:
    parsed = ParsedEmail(text_body="Please login to verify your account to continue.")

    assert "CONTENT-CREDENTIAL-HARVESTING" in _rule_ids(parsed)


def test_unrelated_body_does_not_trigger_credential_rule() -> None:
    parsed = ParsedEmail(text_body="See the attached quarterly report.")

    assert "CONTENT-CREDENTIAL-HARVESTING" not in _rule_ids(parsed)


# --- Payment / invoice scams ---


def test_payment_scam_phrase_triggers_finding() -> None:
    parsed = ParsedEmail(text_body="Your payment is overdue, please remit payment immediately.")

    assert "CONTENT-PAYMENT-SCAM" in _rule_ids(parsed)


def test_unrelated_body_does_not_trigger_payment_rule() -> None:
    parsed = ParsedEmail(text_body="See the attached quarterly report.")

    assert "CONTENT-PAYMENT-SCAM" not in _rule_ids(parsed)


# --- Password reset scams ---


def test_password_reset_phrase_triggers_finding() -> None:
    parsed = ParsedEmail(text_body="Click here to reset your password immediately.")

    assert "CONTENT-PASSWORD-RESET-SCAM" in _rule_ids(parsed)


def test_unrelated_body_does_not_trigger_password_reset_rule() -> None:
    parsed = ParsedEmail(text_body="See the attached quarterly report.")

    assert "CONTENT-PASSWORD-RESET-SCAM" not in _rule_ids(parsed)


# --- Brand impersonation ---


def test_brand_mentioned_from_unrelated_domain_triggers_finding() -> None:
    parsed = ParsedEmail(
        from_address="support@totally-not-paypal.example",
        text_body="Your PayPal account needs verification.",
    )

    assert "CONTENT-BRAND-IMPERSONATION" in _rule_ids(parsed)


def test_brand_mentioned_from_own_domain_does_not_trigger() -> None:
    parsed = ParsedEmail(
        from_address="service@paypal.com",
        text_body="Your PayPal account needs verification.",
    )

    assert "CONTENT-BRAND-IMPERSONATION" not in _rule_ids(parsed)


def test_brand_mentioned_from_subdomain_of_own_domain_does_not_trigger() -> None:
    """Edge case: a legitimate subdomain of the brand's own domain
    (e.g. mail.paypal.com) must not be flagged."""
    parsed = ParsedEmail(
        from_address="service@mail.paypal.com",
        text_body="Your PayPal account needs verification.",
    )

    assert "CONTENT-BRAND-IMPERSONATION" not in _rule_ids(parsed)


def test_no_brand_mention_does_not_trigger() -> None:
    parsed = ParsedEmail(from_address="alice@example.com", text_body="See the attached report.")

    assert "CONTENT-BRAND-IMPERSONATION" not in _rule_ids(parsed)


def test_empty_email_produces_no_findings() -> None:
    assert check_content(ParsedEmail()) == []
