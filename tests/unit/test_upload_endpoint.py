"""Tests for the /upload endpoint (app.api.v1.upload).

Covers both submission modes (pasted text, .eml upload) and the endpoint's
own validation (extension, content-type allow-list, size cap) - independent
of the parser-level tests in tests/unit/test_email_parser_*.py.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1 import upload as upload_module
from app.config import Settings, get_settings
from app.main import app

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture(autouse=True)
def _clear_settings_override() -> Iterator[None]:
    yield
    app.dependency_overrides.pop(get_settings, None)


def test_get_upload_form_renders(client: TestClient) -> None:
    response = client.get("/upload")

    assert response.status_code == 200
    assert "Analyze an email" in response.text


def test_upload_pasted_raw_email_renders_parsed_result(client: TestClient) -> None:
    raw_text = _load("legitimate.eml").decode("utf-8")

    response = client.post("/upload", data={"raw_email_text": raw_text})

    assert response.status_code == 200
    assert "Quarterly report attached" in response.text
    assert "quarterly_report.pdf" in response.text


def test_upload_eml_file_renders_parsed_result(client: TestClient) -> None:
    response = client.post(
        "/upload",
        files={"file": ("phishing.eml", _load("phishing.eml"), "message/rfc822")},
    )

    assert response.status_code == 200
    assert "Urgent: Verify your account now" in response.text
    assert "possibly obfuscated" in response.text


def test_upload_renders_risk_score_and_findings_for_phishing_fixture(client: TestClient) -> None:
    response = client.post(
        "/upload",
        files={"file": ("phishing.eml", _load("phishing.eml"), "message/rfc822")},
    )

    assert response.status_code == 200
    assert "Risk Score:" in response.text
    assert "CRITICAL" in response.text or "HIGH" in response.text
    assert "SPF failed" in response.text
    assert "Total Findings" in response.text
    assert "Total Risk Score" in response.text
    assert "Risk Classification" in response.text


def test_upload_renders_zero_score_for_legitimate_fixture(client: TestClient) -> None:
    response = client.post(
        "/upload",
        files={"file": ("legitimate.eml", _load("legitimate.eml"), "message/rfc822")},
    )

    assert response.status_code == 200
    assert "Risk Score: 0 / 100" in response.text
    assert "LOW" in response.text


def test_upload_rejects_non_eml_filename(client: TestClient) -> None:
    response = client.post(
        "/upload",
        files={"file": ("phishing.exe", _load("phishing.eml"), "application/octet-stream")},
    )

    assert response.status_code == 200
    assert "Only .eml files are accepted." in response.text


def test_upload_rejects_disallowed_content_type(client: TestClient) -> None:
    response = client.post(
        "/upload",
        files={"file": ("phishing.eml", _load("phishing.eml"), "application/zip")},
    )

    assert response.status_code == 200
    assert "Unsupported upload content type" in response.text


def test_upload_rejects_oversized_payload(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        secret_key="test-secret-key", max_email_upload_bytes=10
    )

    response = client.post("/upload", data={"raw_email_text": "Subject: way too long for the cap"})

    assert response.status_code == 200
    assert "exceeds the maximum allowed size" in response.text


def test_upload_with_nothing_submitted_shows_error(client: TestClient) -> None:
    response = client.post("/upload", data={"raw_email_text": ""})

    assert response.status_code == 200
    assert "Paste a raw email or choose an .eml file to upload." in response.text


def test_upload_calls_save_analysis_result_with_the_computed_score(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase 5: a successful parse+score is handed off for persistence -
    verified here without a real database by monkeypatching the save call
    itself (real persistence is covered by
    tests/integration/test_database.py against real PostgreSQL).
    """
    calls: list[dict[str, object]] = []

    def fake_save_analysis_result(
        db: object, *, parsed: object, scoring: object, submitted_by: object
    ) -> None:
        calls.append({"parsed": parsed, "scoring": scoring, "submitted_by": submitted_by})

    monkeypatch.setattr(upload_module, "save_analysis_result", fake_save_analysis_result)

    response = client.post(
        "/upload",
        files={"file": ("phishing.eml", _load("phishing.eml"), "message/rfc822")},
    )

    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0]["parsed"].subject == "Urgent: Verify your account now"  # type: ignore[union-attr]
    assert calls[0]["scoring"].score > 0  # type: ignore[union-attr]
    assert calls[0]["submitted_by"] is None  # not logged in


def test_upload_still_succeeds_when_persistence_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A database outage must not turn a successful analysis into a 500 -
    /upload stays public and functional (Phase 6 decision) regardless of
    database availability; see app/api/v1/upload.py::_persist_analysis.
    """

    def failing_save(*args: object, **kwargs: object) -> None:
        raise SQLAlchemyError("simulated database outage")

    monkeypatch.setattr(upload_module, "save_analysis_result", failing_save)

    response = client.post(
        "/upload",
        files={"file": ("phishing.eml", _load("phishing.eml"), "message/rfc822")},
    )

    assert response.status_code == 200
    assert "Risk Score:" in response.text
    assert "SPF failed" in response.text
