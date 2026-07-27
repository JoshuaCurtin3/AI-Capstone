"""Shared parsing helper for Authentication-Results header values.

Not a rule itself - spf.py/dkim.py/dmarc.py each import this to read their
mechanism's verdict from headers the receiving mail server already added.

Per TASKS.md Phase 4 "SPF/DKIM/DMARC determinism tension": re-verifying
SPF/DKIM/DMARC live would require DNS lookups, which are network-dependent
and can change over time - in tension with CLAUDE.md's determinism
requirement. Parsing the Authentication-Results header the receiving MTA
already computed keeps scoring a pure function of the parsed email.
"""

from __future__ import annotations

import re

_MECHANISM_PATTERNS = {
    "spf": re.compile(r"\bspf=([a-zA-Z]+)", re.IGNORECASE),
    "dkim": re.compile(r"\bdkim=([a-zA-Z]+)", re.IGNORECASE),
    "dmarc": re.compile(r"\bdmarc=([a-zA-Z]+)", re.IGNORECASE),
}


def extract_auth_result(authentication_results: list[str], mechanism: str) -> str | None:
    """Return the first verdict (e.g. "pass", "fail", "none") for `mechanism`.

    Authentication-Results headers are prepended by each hop, so the first
    entry in the list is the one added by the organization's own receiving
    server - the only hop that can be trusted (a later/lower entry could
    have been forged by an upstream relay before it ever reached us).
    """
    pattern = _MECHANISM_PATTERNS[mechanism]
    for header in authentication_results:
        match = pattern.search(header)
        if match:
            return match.group(1).lower()
    return None
