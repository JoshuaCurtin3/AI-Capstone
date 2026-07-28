"""Generate a human-readable explanation for an already-computed risk score.

This module treats the score and triggered rules as read-only input. It must
never return a value that overrides, adjusts, or substitutes for the
numerical score from app.phishing_detection.scoring_engine (see CLAUDE.md).
Every failure path (missing key, timeout, connection error, rate limit,
invalid request, malformed response, any other API error, or an unexpected
exception) is caught here and turned into an ExplanationResult the caller can
render safely - callers never need to catch anthropic exceptions themselves,
and no exception message or API key is ever placed in that result.
"""

from __future__ import annotations

import logging

import anthropic
import pydantic

from app.ai_analysis.client import get_client
from app.ai_analysis.prompts import build_explanation_prompt
from app.ai_analysis.schemas import ExplanationErrorCategory, ExplanationResponse, ExplanationResult
from app.config import Settings, get_settings
from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.schemas import ScoringResult

logger = logging.getLogger(__name__)

#: Shown in place of the AI explanation whenever generate_explanation fails
#: for any reason - the deterministic score/classification/findings remain
#: displayed and authoritative regardless (see CLAUDE.md).
FALLBACK_EXPLANATION_MESSAGE = (
    "AI explanation is currently unavailable. The deterministic analysis remains valid."
)


def generate_explanation(
    scoring: ScoringResult,
    parsed: ParsedEmail,
    *,
    client: anthropic.Anthropic | None = None,
    settings: Settings | None = None,
) -> ExplanationResult:
    """Ask Claude to explain `scoring`, or return a categorized failure.

    `client` is accepted for dependency injection (tests pass a mock so no
    real network call is ever made); when omitted, a real client is built
    from settings via app.ai_analysis.client.get_client.
    """
    settings = settings or get_settings()

    if not settings.anthropic_api_key:
        # No API call is made at all when the key is missing - this is the
        # expected, non-exceptional "not configured" path.
        return ExplanationResult(
            success=False, error_category=ExplanationErrorCategory.NOT_CONFIGURED
        )

    active_client = client if client is not None else get_client(settings)
    if active_client is None:  # pragma: no cover - defensive; mirrors the check above
        return ExplanationResult(
            success=False, error_category=ExplanationErrorCategory.NOT_CONFIGURED
        )

    prompt = build_explanation_prompt(scoring, parsed)

    try:
        response = active_client.messages.parse(
            model=settings.anthropic_model,
            max_tokens=settings.anthropic_max_tokens,
            system=prompt.system,
            messages=[{"role": "user", "content": prompt.user}],
            output_format=ExplanationResponse,
        )
    except anthropic.APITimeoutError:
        logger.warning("Claude explanation request timed out")
        return ExplanationResult(success=False, error_category=ExplanationErrorCategory.TIMEOUT)
    except anthropic.RateLimitError:
        logger.warning("Claude explanation request was rate limited")
        return ExplanationResult(
            success=False, error_category=ExplanationErrorCategory.RATE_LIMITED
        )
    except anthropic.BadRequestError:
        logger.warning("Claude explanation request was rejected as invalid")
        return ExplanationResult(
            success=False, error_category=ExplanationErrorCategory.INVALID_REQUEST
        )
    except anthropic.APIConnectionError:
        logger.warning("Could not connect to the Claude API")
        return ExplanationResult(
            success=False, error_category=ExplanationErrorCategory.CONNECTION_ERROR
        )
    except anthropic.APIStatusError:
        logger.exception("Claude API returned an error")
        return ExplanationResult(success=False, error_category=ExplanationErrorCategory.API_ERROR)
    except pydantic.ValidationError:
        logger.exception("Claude's response did not match the required output schema")
        return ExplanationResult(
            success=False, error_category=ExplanationErrorCategory.MALFORMED_RESPONSE
        )
    except Exception:
        logger.exception("Unexpected error generating AI explanation")
        return ExplanationResult(
            success=False, error_category=ExplanationErrorCategory.UNEXPECTED_ERROR
        )

    parsed_output = response.parsed_output
    explanation_text = parsed_output.explanation.strip() if parsed_output is not None else ""
    if not explanation_text:
        return ExplanationResult(
            success=False, error_category=ExplanationErrorCategory.MALFORMED_RESPONSE
        )

    return ExplanationResult(success=True, explanation=explanation_text)
