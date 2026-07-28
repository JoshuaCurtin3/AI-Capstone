"""Thin wrapper around Anthropic client construction.

Kept separate from prompts.py/services.py so the client can be built (or
swapped for a test double) in one place. app.ai_analysis.services accepts a
`client` parameter for exactly this reason - tests inject a mock there and
never construct a real anthropic.Anthropic(), so no test makes a live API call.
"""

from __future__ import annotations

import anthropic

from app.config import Settings, get_settings


def get_client(settings: Settings | None = None) -> anthropic.Anthropic | None:
    """Build an Anthropic client from settings, or None if unconfigured.

    Returns None rather than raising when ANTHROPIC_API_KEY is unset, so
    callers (app.ai_analysis.services.generate_explanation) can treat "no key"
    as an ordinary fallback case instead of an exceptional API failure - a
    missing key must only disable AI explanations, never break analysis
    (see CLAUDE.md).
    """
    settings = settings or get_settings()
    if not settings.anthropic_api_key:
        return None
    return anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.anthropic_timeout_seconds,
    )
