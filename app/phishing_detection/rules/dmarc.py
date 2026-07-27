"""DMARC authentication rule, plus the missing-Authentication-Results check.

See app.phishing_detection.rules._auth_results for why this reads the
verdict from Authentication-Results instead of re-querying DNS live.
"""

from __future__ import annotations

from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.rules._auth_results import extract_auth_result
from app.phishing_detection.schemas import Finding

DMARC_RULE_ID = "AUTH-DMARC-FAIL"
DMARC_POINTS = 15

MISSING_AUTH_RULE_ID = "AUTH-MISSING-RESULTS"
MISSING_AUTH_POINTS = 10


def check_dmarc(parsed_email: ParsedEmail) -> list[Finding]:
    """Flag a message whose DMARC check the receiving server marked as failed."""
    result = extract_auth_result(parsed_email.authentication_results, "dmarc")
    if result != "fail":
        return []
    return [
        Finding(
            rule_id=DMARC_RULE_ID,
            category="authentication",
            name="DMARC failed",
            points=DMARC_POINTS,
            evidence=f"dmarc={result} in Authentication-Results header",
            explanation=(
                "The message failed DMARC alignment, meaning it did not pass the "
                "sending domain's own published authentication policy."
            ),
        )
    ]


def check_missing_authentication_results(parsed_email: ParsedEmail) -> list[Finding]:
    """Flag a message with no Authentication-Results header at all.

    Without it, SPF/DKIM/DMARC outcomes can't be verified from the parsed
    email at all - that absence is itself a risk signal, separate from any
    individual mechanism failing.
    """
    if parsed_email.authentication_results:
        return []
    return [
        Finding(
            rule_id=MISSING_AUTH_RULE_ID,
            category="authentication",
            name="Missing Authentication-Results header",
            points=MISSING_AUTH_POINTS,
            evidence="No Authentication-Results header present",
            explanation=(
                "The message carries no Authentication-Results header, so SPF, "
                "DKIM, and DMARC outcomes cannot be verified at all."
            ),
        )
    ]
