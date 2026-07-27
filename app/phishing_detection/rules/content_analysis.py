"""Body/subject content detection rules: urgency language, credential
harvesting, payment/invoice scams, password-reset scams, and brand
impersonation keywords.

All matching is plain substring search over the lowercased subject + text
body + HTML source - deterministic and offline, no NLP/LLM involved (see
CLAUDE.md: the scoring path must have zero AI dependence).
"""

from __future__ import annotations

from email.utils import parseaddr

from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.schemas import Finding

_URGENCY_PHRASES = [
    "urgent",
    "immediately",
    "act now",
    "as soon as possible",
    "final notice",
    "action required",
    "expires today",
    "limited time",
    "immediate action",
]

_CREDENTIAL_HARVESTING_PHRASES = [
    "enter your username and password",
    "login to verify your account",
    "confirm your login details",
    "verify your identity",
    "confirm your credentials",
    "sign in to continue",
    "update your account information",
]

_PAYMENT_SCAM_PHRASES = [
    "invoice attached",
    "payment is overdue",
    "wire transfer",
    "outstanding balance",
    "update your payment method",
    "past due",
    "invoice #",
    "remit payment",
]

_PASSWORD_RESET_PHRASES = [
    "reset your password",
    "password has expired",
    "password will expire",
    "click here to reset your password",
    "password reset request",
]

#: Brand keyword -> the domain(s) that brand actually sends mail from. A
#: mention of the brand from a sender domain outside this set is treated as
#: impersonation.
_BRAND_DOMAINS: dict[str, tuple[str, ...]] = {
    "paypal": ("paypal.com",),
    "microsoft": ("microsoft.com",),
    "apple": ("apple.com",),
    "amazon": ("amazon.com",),
    "netflix": ("netflix.com",),
    "docusign": ("docusign.com", "docusign.net"),
    "chase": ("chase.com",),
    "wells fargo": ("wellsfargo.com",),
    "bank of america": ("bankofamerica.com",),
    "google": ("google.com",),
}


def _combined_text(parsed_email: ParsedEmail) -> str:
    parts = [parsed_email.subject or "", parsed_email.text_body or "", parsed_email.html_body or ""]
    return " ".join(parts).lower()


def _from_domain(parsed_email: ParsedEmail) -> str | None:
    _, addr = parseaddr(parsed_email.from_address or "")
    if "@" not in addr:
        return None
    return addr.rsplit("@", 1)[-1].lower()


def _check_phrase_list(
    text: str, phrases: list[str], rule_id: str, name: str, points: int, explanation: str
) -> list[Finding]:
    matches = [phrase for phrase in phrases if phrase in text]
    if not matches:
        return []
    return [
        Finding(
            rule_id=rule_id,
            category="content",
            name=name,
            points=points,
            evidence=", ".join(matches),
            explanation=explanation,
        )
    ]


def _check_brand_impersonation(parsed_email: ParsedEmail, text: str) -> list[Finding]:
    sender_domain = _from_domain(parsed_email)
    matched_brands: list[str] = []
    for brand, domains in _BRAND_DOMAINS.items():
        if brand not in text:
            continue
        sent_from_brand = sender_domain is not None and any(
            sender_domain == domain or sender_domain.endswith(f".{domain}") for domain in domains
        )
        if not sent_from_brand:
            matched_brands.append(brand)
    if not matched_brands:
        return []
    return [
        Finding(
            rule_id="CONTENT-BRAND-IMPERSONATION",
            category="content",
            name="Brand impersonation keywords",
            points=10,
            evidence=(
                f"Mentions {', '.join(matched_brands)}; "
                f"sender domain: {sender_domain or 'unknown'}"
            ),
            explanation=(
                "The message references a well-known brand but was not sent from "
                "that brand's own domain, a common impersonation pattern."
            ),
        )
    ]


def check_content(parsed_email: ParsedEmail) -> list[Finding]:
    """Run every content-based rule and return all triggered findings."""
    text = _combined_text(parsed_email)
    findings: list[Finding] = []
    findings.extend(
        _check_phrase_list(
            text,
            _URGENCY_PHRASES,
            "CONTENT-URGENCY",
            "Urgency language",
            5,
            "The message uses urgency or time-pressure language, a common tactic "
            "to short-circuit careful evaluation.",
        )
    )
    findings.extend(
        _check_phrase_list(
            text,
            _CREDENTIAL_HARVESTING_PHRASES,
            "CONTENT-CREDENTIAL-HARVESTING",
            "Credential harvesting language",
            15,
            "The message asks the recipient to enter or confirm login "
            "credentials, a common phishing objective.",
        )
    )
    findings.extend(
        _check_phrase_list(
            text,
            _PAYMENT_SCAM_PHRASES,
            "CONTENT-PAYMENT-SCAM",
            "Payment or invoice scam language",
            10,
            "The message references an invoice or payment in a way consistent "
            "with common invoice-fraud scams.",
        )
    )
    findings.extend(
        _check_phrase_list(
            text,
            _PASSWORD_RESET_PHRASES,
            "CONTENT-PASSWORD-RESET-SCAM",
            "Password reset scam language",
            10,
            "The message mimics a password reset notification, a common "
            "pretext to harvest credentials via a fake reset link.",
        )
    )
    findings.extend(_check_brand_impersonation(parsed_email, text))
    return findings
