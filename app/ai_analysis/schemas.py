"""Typed structures for this app's Claude API input/output.

`ExplanationResponse` is deliberately narrow - it is the JSON schema Claude's
structured output is constrained to (see app.ai_analysis.services), and it has
no field that could be mistaken for or feed into a score. Even if injected
email content convinces the model to try to emit a score, there is no slot in
this schema for it to land in, and `extra="forbid"` rejects it outright if it
tries anyway (see CLAUDE.md's core rule).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ExplanationResponse(BaseModel):
    """The only shape Claude's structured output is allowed to take."""

    model_config = ConfigDict(extra="forbid")

    explanation: str


class ExplanationErrorCategory(StrEnum):
    """Why `generate_explanation` could not produce an explanation.

    Never carries the raw exception message - see
    app.ai_analysis.services.generate_explanation, which logs the real error
    server-side but returns only this category to callers/templates.
    """

    NOT_CONFIGURED = "not_configured"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    RATE_LIMITED = "rate_limited"
    INVALID_REQUEST = "invalid_request"
    MALFORMED_RESPONSE = "malformed_response"
    API_ERROR = "api_error"
    UNEXPECTED_ERROR = "unexpected_error"


class ExplanationResult(BaseModel):
    """Structured success/failure result returned by `generate_explanation`."""

    success: bool
    explanation: str | None = None
    error_category: ExplanationErrorCategory | None = None
