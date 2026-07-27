"""SPF authentication rule.

See app.phishing_detection.rules._auth_results for why this reads the
verdict from Authentication-Results instead of re-querying DNS live.
"""

from __future__ import annotations

from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.rules._auth_results import extract_auth_result
from app.phishing_detection.schemas import Finding

RULE_ID = "AUTH-SPF-FAIL"
POINTS = 15


def check_spf(parsed_email: ParsedEmail) -> list[Finding]:
    """Flag a message whose SPF check the receiving server marked as failed."""
    result = extract_auth_result(parsed_email.authentication_results, "spf")
    if result != "fail":
        return []
    return [
        Finding(
            rule_id=RULE_ID,
            category="authentication",
            name="SPF failed",
            points=POINTS,
            evidence=f"spf={result} in Authentication-Results header",
            explanation=(
                "The sending server failed SPF authentication, meaning it was not "
                "authorized to send mail on behalf of the claimed domain."
            ),
        )
    ]
