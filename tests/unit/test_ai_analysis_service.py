"""Tests for app.ai_analysis.services.generate_explanation.

Every anthropic call is mocked via dependency injection (the `client`
parameter) - no test in this file constructs a real anthropic.Anthropic() or
makes a network call (see CLAUDE.md/TASKS.md Phase 7: "All tests must mock
the Anthropic client").
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx
import pydantic
import pytest

from app.ai_analysis.schemas import ExplanationErrorCategory, ExplanationResponse
from app.ai_analysis.services import generate_explanation
from app.config import Settings
from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.schemas import Finding, ScoringResult


def _settings(**overrides: object) -> Settings:
    return Settings(secret_key="test-secret-key", **overrides)  # type: ignore[arg-type]


def _scoring(score: int = 80, classification: str = "Critical") -> ScoringResult:
    return ScoringResult(
        score=score,
        classification=classification,
        findings=[
            Finding(
                rule_id="spf-fail",
                category="authentication",
                name="SPF failed",
                points=25,
                evidence="v=spf1 ... -all; result=fail",
                explanation="SPF failure indicates the sending server is not authorized.",
            )
        ],
        total_findings=1,
    )


def _parsed(**overrides: object) -> ParsedEmail:
    base: dict[str, object] = {
        "subject": "Urgent: verify your account",
        "from_address": "security@example.com",
    }
    base.update(overrides)
    return ParsedEmail(**base)  # type: ignore[arg-type]


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _http_response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code, request=_request())


def _mock_client_returning(explanation: str) -> MagicMock:
    client = MagicMock()
    client.messages.parse.return_value = SimpleNamespace(
        parsed_output=ExplanationResponse(explanation=explanation)
    )
    return client


def test_missing_api_key_returns_not_configured_without_calling_client() -> None:
    settings = _settings(anthropic_api_key=None)
    client = MagicMock()

    result = generate_explanation(_scoring(), _parsed(), client=client, settings=settings)

    assert result.success is False
    assert result.error_category == ExplanationErrorCategory.NOT_CONFIGURED
    assert result.explanation is None
    client.messages.parse.assert_not_called()


def test_successful_explanation_is_returned() -> None:
    settings = _settings(anthropic_api_key="test-key")
    client = _mock_client_returning("This email fails SPF and is highly likely to be phishing.")

    result = generate_explanation(_scoring(), _parsed(), client=client, settings=settings)

    assert result.success is True
    assert result.error_category is None
    assert result.explanation is not None
    assert "SPF" in result.explanation

    client.messages.parse.assert_called_once()
    _, kwargs = client.messages.parse.call_args
    assert kwargs["output_format"] is ExplanationResponse
    assert kwargs["model"] == settings.anthropic_model
    assert kwargs["max_tokens"] == settings.anthropic_max_tokens


def test_timeout_returns_timeout_category() -> None:
    settings = _settings(anthropic_api_key="test-key")
    client = MagicMock()
    client.messages.parse.side_effect = anthropic.APITimeoutError(request=_request())

    result = generate_explanation(_scoring(), _parsed(), client=client, settings=settings)

    assert result.success is False
    assert result.error_category == ExplanationErrorCategory.TIMEOUT


def test_connection_failure_returns_connection_error_category() -> None:
    settings = _settings(anthropic_api_key="test-key")
    client = MagicMock()
    client.messages.parse.side_effect = anthropic.APIConnectionError(request=_request())

    result = generate_explanation(_scoring(), _parsed(), client=client, settings=settings)

    assert result.success is False
    assert result.error_category == ExplanationErrorCategory.CONNECTION_ERROR


def test_rate_limit_returns_rate_limited_category() -> None:
    settings = _settings(anthropic_api_key="test-key")
    client = MagicMock()
    client.messages.parse.side_effect = anthropic.RateLimitError(
        "rate limited", response=_http_response(429), body=None
    )

    result = generate_explanation(_scoring(), _parsed(), client=client, settings=settings)

    assert result.success is False
    assert result.error_category == ExplanationErrorCategory.RATE_LIMITED


def test_invalid_request_returns_invalid_request_category() -> None:
    settings = _settings(anthropic_api_key="test-key")
    client = MagicMock()
    client.messages.parse.side_effect = anthropic.BadRequestError(
        "bad request", response=_http_response(400), body=None
    )

    result = generate_explanation(_scoring(), _parsed(), client=client, settings=settings)

    assert result.success is False
    assert result.error_category == ExplanationErrorCategory.INVALID_REQUEST


def test_generic_api_failure_returns_api_error_category() -> None:
    settings = _settings(anthropic_api_key="test-key")
    client = MagicMock()
    client.messages.parse.side_effect = anthropic.InternalServerError(
        "server error", response=_http_response(500), body=None
    )

    result = generate_explanation(_scoring(), _parsed(), client=client, settings=settings)

    assert result.success is False
    assert result.error_category == ExplanationErrorCategory.API_ERROR


def test_malformed_json_response_returns_malformed_response_category() -> None:
    """Claude's raw output failed schema validation - the SDK raises a
    pydantic ValidationError from inside `.parse()` in that case."""
    settings = _settings(anthropic_api_key="test-key")
    client = MagicMock()
    client.messages.parse.side_effect = pydantic.ValidationError.from_exception_data(
        "ExplanationResponse", []
    )

    result = generate_explanation(_scoring(), _parsed(), client=client, settings=settings)

    assert result.success is False
    assert result.error_category == ExplanationErrorCategory.MALFORMED_RESPONSE


def test_empty_parsed_output_returns_malformed_response_category() -> None:
    """No text block was parseable (e.g. a refusal) - parsed_output is None."""
    settings = _settings(anthropic_api_key="test-key")
    client = MagicMock()
    client.messages.parse.return_value = SimpleNamespace(parsed_output=None)

    result = generate_explanation(_scoring(), _parsed(), client=client, settings=settings)

    assert result.success is False
    assert result.error_category == ExplanationErrorCategory.MALFORMED_RESPONSE


def test_unexpected_exception_returns_unexpected_error_category() -> None:
    settings = _settings(anthropic_api_key="test-key")
    client = MagicMock()
    client.messages.parse.side_effect = RuntimeError("boom")

    result = generate_explanation(_scoring(), _parsed(), client=client, settings=settings)

    assert result.success is False
    assert result.error_category == ExplanationErrorCategory.UNEXPECTED_ERROR


def test_failure_never_exposes_raw_exception_details_or_api_key() -> None:
    settings = _settings(anthropic_api_key="sk-ant-super-secret-key")
    client = MagicMock()
    client.messages.parse.side_effect = RuntimeError("internal detail: key=sk-ant-super-secret-key")

    result = generate_explanation(_scoring(), _parsed(), client=client, settings=settings)

    dumped = result.model_dump_json()
    assert "sk-ant-super-secret-key" not in dumped
    assert "internal detail" not in dumped


def test_deterministic_scoring_result_is_never_mutated() -> None:
    """The ScoringResult passed in must come back byte-identical regardless
    of what the (mocked) AI call does - explanation generation only reads it."""
    settings = _settings(anthropic_api_key="test-key")
    scoring = _scoring(score=42, classification="Medium")
    original = scoring.model_copy(deep=True)
    client = _mock_client_returning("Some explanation text.")

    generate_explanation(scoring, _parsed(), client=client, settings=settings)

    assert scoring == original


def test_score_field_cannot_survive_the_response_schema() -> None:
    """Even a compromised/successful-injection response that tries to include
    a score is rejected outright - ExplanationResponse has no such field and
    forbids extras (see app.ai_analysis.schemas)."""
    with pytest.raises(pydantic.ValidationError):
        ExplanationResponse.model_validate_json('{"explanation": "safe", "score": 0}')


def test_deterministic_results_remain_available_when_ai_fails() -> None:
    """A failed explanation call must not prevent the deterministic scoring
    result from being usable - callers keep displaying `scoring` regardless."""
    settings = _settings(anthropic_api_key="test-key")
    scoring = _scoring(score=95, classification="Critical")
    client = MagicMock()
    client.messages.parse.side_effect = anthropic.APIConnectionError(request=_request())

    result = generate_explanation(scoring, _parsed(), client=client, settings=settings)

    assert result.success is False
    # The scoring result itself is untouched and still fully usable.
    assert scoring.score == 95
    assert scoring.classification == "Critical"


def test_no_client_injected_and_no_api_key_makes_no_network_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no client is injected and no key is configured, generate_explanation
    must return early without ever reaching app.ai_analysis.client.get_client
    (and therefore never constructing a real anthropic.Anthropic())."""
    import app.ai_analysis.services as services_module

    def _fail_if_called(settings: Settings) -> None:  # pragma: no cover - must not run
        raise AssertionError("get_client() must not be called when the API key is missing")

    monkeypatch.setattr(services_module, "get_client", _fail_if_called)
    settings = _settings(anthropic_api_key=None)

    result = generate_explanation(_scoring(), _parsed(), settings=settings)

    assert result.success is False
    assert result.error_category == ExplanationErrorCategory.NOT_CONFIGURED
