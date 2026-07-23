"""Header extraction tests for app.email_parser.parser.parse_email."""

from __future__ import annotations

from pathlib import Path

from app.email_parser.parser import parse_email

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_parses_headers_from_well_formed_email() -> None:
    parsed = parse_email(_load("legitimate.eml"))

    assert parsed.subject == "Quarterly report attached"
    assert parsed.from_address == "Alice Example <alice@example.com>"
    assert parsed.to_addresses == ["Bob Example <bob@example.com>"]
    assert parsed.date == "Mon, 21 Jul 2025 10:15:00 -0400"
    assert parsed.reply_to == "alice@example.com"
    assert parsed.return_path == "<alice@example.com>"
    assert parsed.message_id == "<abc123@example.com>"
    assert len(parsed.authentication_results) == 1
    assert "spf=pass" in parsed.authentication_results[0]
    assert len(parsed.received_headers) == 1
    assert "mail.example.com" in parsed.received_headers[0]


def test_preserves_order_and_captures_every_received_and_auth_results_header() -> None:
    """A message can hop through multiple servers - every Received and
    Authentication-Results header must be kept, in header order."""
    parsed = parse_email(_load("phishing.eml"))

    assert len(parsed.received_headers) == 2
    assert "id 2" in parsed.received_headers[0]
    assert "id 3" in parsed.received_headers[1]
    assert len(parsed.authentication_results) == 1
    assert "spf=fail" in parsed.authentication_results[0]


def test_missing_optional_headers_are_none_or_empty() -> None:
    """A minimal message with only required headers must not crash on the
    optional ones - they should come back as None / empty list, not raise."""
    raw = b"Subject: Just a subject\r\n\r\nBody text.\r\n"

    parsed = parse_email(raw)

    assert parsed.subject == "Just a subject"
    assert parsed.from_address is None
    assert parsed.to_addresses == []
    assert parsed.reply_to is None
    assert parsed.return_path is None
    assert parsed.message_id is None
    assert parsed.authentication_results == []
    assert parsed.received_headers == []


def test_malformed_email_does_not_raise_and_still_extracts_headers() -> None:
    """A structurally broken body (declared multipart boundary that never
    appears) must not crash parsing - headers should still come through."""
    parsed = parse_email(_load("malformed.eml"))

    assert parsed.subject == "Broken message"
    assert parsed.from_address == "broken@example.com"
    assert parsed.date == "not-a-real-date"
    # The broken multipart body yields no usable content, not a crash.
    assert parsed.text_body is None
    assert parsed.html_body is None
    assert parsed.attachments == []
