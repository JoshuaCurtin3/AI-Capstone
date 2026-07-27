"""URL-based detection rules: IP-literal hosts, punycode, shorteners,
suspicious TLDs, insecure HTTP, and display-text/destination mismatches.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from app.email_parser.schemas import ParsedEmail, ParsedURL
from app.phishing_detection.schemas import Finding

_SHORTENER_DOMAINS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "ow.ly",
    "is.gd",
    "buff.ly",
    "rebrand.ly",
    "cutt.ly",
    "shorturl.at",
    "rb.gy",
    "tiny.cc",
}

#: TLDs that carry disproportionately high spam/phishing abuse rates in
#: public abuse-report data - not exhaustive, just a deterministic signal.
_SUSPICIOUS_TLDS = {
    "zip",
    "review",
    "country",
    "kim",
    "cricket",
    "science",
    "work",
    "party",
    "gq",
    "tk",
    "ml",
    "cf",
    "ga",
    "xyz",
    "top",
    "link",
    "click",
}


def _hostname(url: str) -> str | None:
    host = urlparse(url).hostname
    return host.lower() if host else None


def _is_ip_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _matches_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _check_ip_urls(urls: list[ParsedURL]) -> list[Finding]:
    matches = [u.url for u in urls if (host := _hostname(u.url)) and _is_ip_host(host)]
    if not matches:
        return []
    return [
        Finding(
            rule_id="URL-IP-ADDRESS",
            category="url",
            name="URL uses an IP address",
            points=20,
            evidence=", ".join(matches),
            explanation=(
                "Legitimate companies rarely send users directly to IP addresses "
                "instead of a named domain."
            ),
        )
    ]


def _check_punycode(urls: list[ParsedURL]) -> list[Finding]:
    matches = [u.url for u in urls if (host := _hostname(u.url)) and "xn--" in host]
    if not matches:
        return []
    return [
        Finding(
            rule_id="URL-PUNYCODE",
            category="url",
            name="Punycode domain",
            points=15,
            evidence=", ".join(matches),
            explanation=(
                "Punycode ('xn--') domains can visually impersonate a trusted "
                "brand using look-alike characters."
            ),
        )
    ]


def _check_shorteners(urls: list[ParsedURL]) -> list[Finding]:
    matches = [
        u.url
        for u in urls
        if (host := _hostname(u.url))
        and any(_matches_domain(host, domain) for domain in _SHORTENER_DOMAINS)
    ]
    if not matches:
        return []
    return [
        Finding(
            rule_id="URL-SHORTENER",
            category="url",
            name="URL shortener used",
            points=10,
            evidence=", ".join(matches),
            explanation=(
                "URL shorteners hide the true destination of a link, a common "
                "technique to bypass casual inspection."
            ),
        )
    ]


def _check_suspicious_tld(urls: list[ParsedURL]) -> list[Finding]:
    matches: list[str] = []
    for u in urls:
        host = _hostname(u.url)
        if not host or _is_ip_host(host):
            continue
        tld = host.rsplit(".", 1)[-1]
        if tld in _SUSPICIOUS_TLDS:
            matches.append(u.url)
    if not matches:
        return []
    return [
        Finding(
            rule_id="URL-SUSPICIOUS-TLD",
            category="url",
            name="Suspicious top-level domain",
            points=10,
            evidence=", ".join(matches),
            explanation=(
                "This top-level domain is disproportionately associated with spam "
                "and phishing campaigns."
            ),
        )
    ]


def _check_http(urls: list[ParsedURL]) -> list[Finding]:
    matches = [u.url for u in urls if urlparse(u.url).scheme == "http"]
    if not matches:
        return []
    return [
        Finding(
            rule_id="URL-INSECURE-HTTP",
            category="url",
            name="Insecure HTTP link",
            points=5,
            evidence=", ".join(matches),
            explanation=(
                "The link uses plain HTTP instead of HTTPS, offering no transport "
                "encryption and no certificate-based identity check."
            ),
        )
    ]


def _check_domain_mismatch(urls: list[ParsedURL]) -> list[Finding]:
    """Reuse the parser's own display-text-vs-href comparison
    (ParsedURL.is_obfuscated) rather than recomputing it here.
    """
    matches = [u.url for u in urls if u.is_obfuscated]
    if not matches:
        return []
    return [
        Finding(
            rule_id="URL-DISPLAY-MISMATCH",
            category="url",
            name="Displayed link text does not match destination",
            points=15,
            evidence=", ".join(matches),
            explanation=(
                "The visible link text names a different domain than where the "
                "link actually leads, a classic phishing disguise."
            ),
        )
    ]


def check_urls(parsed_email: ParsedEmail) -> list[Finding]:
    """Run every URL-based rule and return all triggered findings."""
    urls = parsed_email.urls
    findings: list[Finding] = []
    findings.extend(_check_ip_urls(urls))
    findings.extend(_check_punycode(urls))
    findings.extend(_check_shorteners(urls))
    findings.extend(_check_suspicious_tld(urls))
    findings.extend(_check_http(urls))
    findings.extend(_check_domain_mismatch(urls))
    return findings
