"""Header-based detection rules: sender/reply-to/return-path mismatches,
suspicious display names, and excessive relay chains.
"""

from __future__ import annotations

from email.utils import parseaddr

from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.schemas import Finding

#: Above this many Received headers, a relay chain is unusually long for a
#: normal delivery path - generous enough to avoid flagging legitimate
#: large-org routing.
RECEIVED_HEADER_THRESHOLD = 8


def _domain_of(address: str | None) -> str | None:
    """Extract the lowercased domain from a header value like "Name <a@b.com>"."""
    if not address:
        return None
    _, addr = parseaddr(address)
    if "@" not in addr:
        return None
    return addr.rsplit("@", 1)[-1].lower()


def _check_reply_to_mismatch(parsed_email: ParsedEmail) -> list[Finding]:
    from_domain = _domain_of(parsed_email.from_address)
    reply_domain = _domain_of(parsed_email.reply_to)
    if not from_domain or not reply_domain or from_domain == reply_domain:
        return []
    return [
        Finding(
            rule_id="HDR-REPLYTO-MISMATCH",
            category="header",
            name="Reply-To mismatch",
            points=10,
            evidence=f"From domain '{from_domain}' vs Reply-To domain '{reply_domain}'",
            explanation=(
                "Replies are directed to a different domain than the sender, a "
                "common way to redirect victim responses to an attacker-controlled "
                "address."
            ),
        )
    ]


def _check_return_path_mismatch(parsed_email: ParsedEmail) -> list[Finding]:
    from_domain = _domain_of(parsed_email.from_address)
    return_domain = _domain_of(parsed_email.return_path)
    if not from_domain or not return_domain or from_domain == return_domain:
        return []
    return [
        Finding(
            rule_id="HDR-RETURNPATH-MISMATCH",
            category="header",
            name="Return-Path mismatch",
            points=10,
            evidence=f"From domain '{from_domain}' vs Return-Path domain '{return_domain}'",
            explanation=(
                "Bounce messages are routed to a different domain than the sender, "
                "which can indicate the message was sent through unauthorized "
                "infrastructure."
            ),
        )
    ]


def _check_suspicious_display_name(parsed_email: ParsedEmail) -> list[Finding]:
    """Flag a From display name that embeds a different email domain than
    the address it's actually attached to, e.g.
    `"security@paypal.com" <attacker@evil.example>`.
    """
    display_name, addr = parseaddr(parsed_email.from_address or "")
    if not display_name or "@" not in display_name:
        return []
    embedded_domain = display_name.rsplit("@", 1)[-1].strip(" \"'<>").lower()
    actual_domain = addr.rsplit("@", 1)[-1].lower() if "@" in addr else None
    if not actual_domain or not embedded_domain or embedded_domain == actual_domain:
        return []
    return [
        Finding(
            rule_id="HDR-SUSPICIOUS-DISPLAY-NAME",
            category="header",
            name="Suspicious display name",
            points=10,
            evidence=f"Display name '{display_name}' vs actual sender domain '{actual_domain}'",
            explanation=(
                "The sender's display name embeds an email address or domain that "
                "differs from the actual sending address, a common impersonation "
                "technique."
            ),
        )
    ]


def _check_excessive_received_headers(parsed_email: ParsedEmail) -> list[Finding]:
    count = len(parsed_email.received_headers)
    if count <= RECEIVED_HEADER_THRESHOLD:
        return []
    return [
        Finding(
            rule_id="HDR-EXCESSIVE-RECEIVED",
            category="header",
            name="Excessive Received headers",
            points=5,
            evidence=f"{count} Received headers (threshold: {RECEIVED_HEADER_THRESHOLD})",
            explanation=(
                "An unusually long chain of mail relays can indicate the message "
                "was routed through compromised or abused infrastructure."
            ),
        )
    ]


def check_headers(parsed_email: ParsedEmail) -> list[Finding]:
    """Run every header-based rule and return all triggered findings."""
    findings: list[Finding] = []
    findings.extend(_check_reply_to_mismatch(parsed_email))
    findings.extend(_check_return_path_mismatch(parsed_email))
    findings.extend(_check_suspicious_display_name(parsed_email))
    findings.extend(_check_excessive_received_headers(parsed_email))
    return findings
