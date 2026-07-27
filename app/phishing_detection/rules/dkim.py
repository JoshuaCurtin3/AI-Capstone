"""DKIM authentication rule.

See app.phishing_detection.rules._auth_results for why this reads the
verdict from Authentication-Results instead of re-verifying the signature
live.
"""

from __future__ import annotations

from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.rules._auth_results import extract_auth_result
from app.phishing_detection.schemas import Finding

RULE_ID = "AUTH-DKIM-FAIL"
POINTS = 15


def check_dkim(parsed_email: ParsedEmail) -> list[Finding]:
    """Flag a message whose DKIM check the receiving server marked as failed."""
    result = extract_auth_result(parsed_email.authentication_results, "dkim")
    if result != "fail":
        return []
    return [
        Finding(
            rule_id=RULE_ID,
            category="authentication",
            name="DKIM failed",
            points=POINTS,
            evidence=f"dkim={result} in Authentication-Results header",
            explanation=(
                "The message's DKIM signature failed verification, meaning its "
                "content or headers may have been altered in transit, or it was "
                "never actually signed by the claimed domain."
            ),
        )
    ]
