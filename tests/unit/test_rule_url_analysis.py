"""Unit tests for app.phishing_detection.rules.url_analysis."""

from __future__ import annotations

from app.email_parser.schemas import ParsedEmail, ParsedURL
from app.phishing_detection.rules.url_analysis import check_urls


def _rule_ids(urls: list[ParsedURL]) -> set[str]:
    return {f.rule_id for f in check_urls(ParsedEmail(urls=urls))}


# --- IP address URLs ---


def test_ipv4_url_triggers_finding() -> None:
    urls = [ParsedURL(url="http://192.168.1.1/login", source="text")]

    assert "URL-IP-ADDRESS" in _rule_ids(urls)


def test_ipv6_url_triggers_finding() -> None:
    """Edge case: an IPv6 literal host should also be flagged, not just IPv4."""
    urls = [ParsedURL(url="http://[2001:db8::1]/login", source="text")]

    assert "URL-IP-ADDRESS" in _rule_ids(urls)


def test_named_domain_url_does_not_trigger_ip_rule() -> None:
    urls = [ParsedURL(url="https://example.com/login", source="text")]

    assert "URL-IP-ADDRESS" not in _rule_ids(urls)


# --- Punycode ---


def test_punycode_domain_triggers_finding() -> None:
    urls = [ParsedURL(url="https://xn--pypal-4ve.com/login", source="text")]

    assert "URL-PUNYCODE" in _rule_ids(urls)


def test_plain_domain_does_not_trigger_punycode_rule() -> None:
    urls = [ParsedURL(url="https://example.com/login", source="text")]

    assert "URL-PUNYCODE" not in _rule_ids(urls)


# --- URL shorteners ---


def test_known_shortener_triggers_finding() -> None:
    urls = [ParsedURL(url="https://bit.ly/abc123", source="text")]

    assert "URL-SHORTENER" in _rule_ids(urls)


def test_shortener_subdomain_triggers_finding() -> None:
    """Edge case: a subdomain of a known shortener (e.g. custom.bit.ly) still counts."""
    urls = [ParsedURL(url="https://custom.bit.ly/abc123", source="text")]

    assert "URL-SHORTENER" in _rule_ids(urls)


def test_lookalike_domain_does_not_trigger_shortener_rule() -> None:
    """Edge case: "mybit.ly" is a different registrable domain than "bit.ly"
    and must not match via naive substring search."""
    urls = [ParsedURL(url="https://mybit.ly/abc123", source="text")]

    assert "URL-SHORTENER" not in _rule_ids(urls)


# --- Suspicious TLDs ---


def test_suspicious_tld_triggers_finding() -> None:
    urls = [ParsedURL(url="https://free-prize.xyz/claim", source="text")]

    assert "URL-SUSPICIOUS-TLD" in _rule_ids(urls)


def test_common_tld_does_not_trigger() -> None:
    urls = [ParsedURL(url="https://example.com/claim", source="text")]

    assert "URL-SUSPICIOUS-TLD" not in _rule_ids(urls)


def test_ip_host_does_not_double_count_as_suspicious_tld() -> None:
    """Edge case: an IP-literal host has no TLD to evaluate - must not crash
    or false-positive the TLD rule."""
    urls = [ParsedURL(url="http://192.168.1.1/claim", source="text")]

    assert "URL-SUSPICIOUS-TLD" not in _rule_ids(urls)


# --- HTTP instead of HTTPS ---


def test_http_url_triggers_finding() -> None:
    urls = [ParsedURL(url="http://example.com/login", source="text")]

    assert "URL-INSECURE-HTTP" in _rule_ids(urls)


def test_https_url_does_not_trigger() -> None:
    urls = [ParsedURL(url="https://example.com/login", source="text")]

    assert "URL-INSECURE-HTTP" not in _rule_ids(urls)


# --- Display text / destination mismatch ---


def test_obfuscated_url_triggers_domain_mismatch_finding() -> None:
    urls = [
        ParsedURL(
            url="http://evil.example/login",
            display_text="https://example.com/login",
            source="html",
            is_obfuscated=True,
        )
    ]

    assert "URL-DISPLAY-MISMATCH" in _rule_ids(urls)


def test_non_obfuscated_url_does_not_trigger_mismatch_rule() -> None:
    urls = [
        ParsedURL(
            url="https://example.com/login",
            display_text="click here",
            source="html",
            is_obfuscated=False,
        )
    ]

    assert "URL-DISPLAY-MISMATCH" not in _rule_ids(urls)


def test_no_urls_produces_no_findings() -> None:
    assert check_urls(ParsedEmail(urls=[])) == []
