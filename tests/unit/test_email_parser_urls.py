"""URL extraction tests for app.email_parser.parser.parse_email."""

from __future__ import annotations

from pathlib import Path

from app.email_parser.parser import parse_email

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_extracts_bare_url_from_plain_text_body_without_trailing_punctuation() -> None:
    parsed = parse_email(_load("legitimate.eml"))

    text_urls = [u for u in parsed.urls if u.source == "text"]
    assert len(text_urls) == 1
    assert text_urls[0].url == "https://example.com/reports/q2"
    assert text_urls[0].is_obfuscated is False


def test_extracts_anchor_url_and_display_text_from_html_body_non_obfuscated() -> None:
    """Display text that isn't itself a URL/domain must never be flagged as
    obfuscated, even though it differs textually from the href."""
    parsed = parse_email(_load("legitimate.eml"))

    html_urls = [u for u in parsed.urls if u.source == "html"]
    assert len(html_urls) == 1
    assert html_urls[0].url == "https://example.com/reports/q2"
    assert html_urls[0].display_text == "our reports page"
    assert html_urls[0].is_obfuscated is False


def test_flags_obfuscated_link_when_display_text_domain_differs_from_href() -> None:
    """Classic phishing pattern: visible text reads as a trusted URL while
    the actual href points somewhere else - must be flagged."""
    parsed = parse_email(_load("phishing.eml"))

    obfuscated = [u for u in parsed.urls if u.is_obfuscated]
    assert len(obfuscated) == 1
    assert obfuscated[0].url == "http://phish.evil-example.net/login"
    assert obfuscated[0].display_text == "https://secure-bank.com/login"

    # The display-text URL is also independently discovered by the bare-URL
    # scan of the HTML body - it must not itself be marked obfuscated.
    bare_html_matches = [u for u in parsed.urls if u.url == "https://secure-bank.com/login"]
    assert len(bare_html_matches) == 1
    assert bare_html_matches[0].is_obfuscated is False


def test_no_urls_returns_empty_list() -> None:
    raw = b"Subject: No links here\r\nFrom: a@example.com\r\n\r\nJust plain words, no links.\r\n"

    parsed = parse_email(raw)

    assert parsed.urls == []


def test_deduplicates_identical_urls_from_the_same_source() -> None:
    raw = (
        b"Subject: Repeats\r\n"
        b"From: a@example.com\r\n"
        b"Content-Type: text/plain\r\n\r\n"
        b"Visit https://example.com/x and again https://example.com/x please.\r\n"
    )

    parsed = parse_email(raw)

    assert [u.url for u in parsed.urls] == ["https://example.com/x"]
