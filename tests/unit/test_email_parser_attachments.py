"""Attachment metadata extraction tests for
app.email_parser.parser.parse_email.

These only ever assert on metadata (filename, content-type, size, hash) -
never on attachment content being opened, written to disk, or executed.
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest

from app.email_parser.exceptions import EmailParsingError
from app.email_parser.parser import parse_email

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_extracts_attachment_filename_type_size_and_hash() -> None:
    parsed = parse_email(_load("legitimate.eml"))

    assert len(parsed.attachments) == 1
    attachment = parsed.attachments[0]

    expected_payload = base64.b64decode(
        "JVBERi0xLjQKJeLjz9MKMSAwIG9iago8PC9UeXBlL0NhdGFsb2c+PgplbmRvYmoK"
    )
    assert attachment.filename == "quarterly_report.pdf"
    assert attachment.content_type == "application/pdf"
    assert attachment.size_bytes == len(expected_payload)
    assert attachment.sha256 == hashlib.sha256(expected_payload).hexdigest()
    assert len(attachment.sha256) == 64


def test_sanitizes_attachment_filename_with_double_extension() -> None:
    """A filename like invoice.pdf.exe must come through as-is (just the
    basename) - the parser doesn't guess intent, only reports metadata."""
    parsed = parse_email(_load("phishing.eml"))

    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].filename == "invoice.pdf.exe"
    assert parsed.attachments[0].content_type == "application/octet-stream"


def test_path_traversal_in_attachment_filename_is_stripped_to_basename() -> None:
    raw = (
        b"Subject: Path traversal attempt\r\n"
        b"From: attacker@example.com\r\n"
        b"MIME-Version: 1.0\r\n"
        b'Content-Type: multipart/mixed; boundary="B"\r\n'
        b"\r\n"
        b"--B\r\n"
        b"Content-Type: text/plain\r\n\r\n"
        b"body\r\n"
        b"--B\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b'Content-Disposition: attachment; filename="../../etc/evil.sh"\r\n'
        b"Content-Transfer-Encoding: base64\r\n\r\n"
        b"ZXZpbA==\r\n"
        b"--B--\r\n"
    )

    parsed = parse_email(raw)

    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].filename == "evil.sh"
    assert ".." not in parsed.attachments[0].filename
    assert "/" not in parsed.attachments[0].filename


def test_no_attachments_returns_empty_list() -> None:
    raw = b"Subject: No attachments\r\nFrom: a@example.com\r\n\r\nJust a body.\r\n"

    parsed = parse_email(raw)

    assert parsed.attachments == []


def test_email_exceeding_max_bytes_is_rejected_before_parsing() -> None:
    """Bounds total input size so header/body/attachment extraction never
    has to operate on an unbounded amount of decoded data."""
    raw = _load("legitimate.eml")

    with pytest.raises(EmailParsingError):
        parse_email(raw, max_bytes=10)
