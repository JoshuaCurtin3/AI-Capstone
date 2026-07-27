"""Attachment metadata extraction tests for
app.email_parser.parser.parse_email.

These only ever assert on metadata (filename, content-type, size, hash) -
never on attachment content being opened, written to disk, or executed.
"""

from __future__ import annotations

import base64
import hashlib
import io
import struct
import zipfile
from email.message import EmailMessage
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


def _build_email_with_attachment(
    filename: str, maintype: str, subtype: str, payload: bytes
) -> bytes:
    message = EmailMessage()
    message["From"] = "sender@example.com"
    message["Subject"] = "Attachment test"
    message.set_content("body")
    message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)
    return message.as_bytes()


def _flag_zip_as_encrypted(data: bytes) -> bytes:
    """Set the ZIP general-purpose encryption bit (bit 0) on every local
    file header and central directory record in `data`.

    zipfile.ZipFile's own write path always recomputes flag_bits from
    scratch (it ignores whatever ZipInfo.flag_bits was set to beforehand),
    so the stdlib can't create a "flagged" fixture directly - this patches
    the already-written bytes instead, purely to exercise
    _detect_zip_password_protection's read path in a test.
    """
    buffer = bytearray(data)
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        index = buffer.find(signature)
        while index != -1:
            offset = index + flag_offset
            current_flags = struct.unpack_from("<H", buffer, offset)[0]
            struct.pack_into("<H", buffer, offset, current_flags | 0x1)
            index = buffer.find(signature, index + 4)
    return bytes(buffer)


def test_password_protected_zip_attachment_is_detected() -> None:
    """Phase 4 attachment rule needs this signal - detected here (not
    re-implemented in phishing_detection) since only the parser ever sees
    the decoded attachment bytes; see AttachmentMeta.is_password_protected.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("secret.txt", b"placeholder - not real encrypted bytes")
    encrypted_zip_bytes = _flag_zip_as_encrypted(buffer.getvalue())
    raw = _build_email_with_attachment("secret.zip", "application", "zip", encrypted_zip_bytes)

    parsed = parse_email(raw)

    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].is_password_protected is True


def test_non_protected_zip_attachment_is_detected_as_such() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("hello.txt", b"hello world")
    raw = _build_email_with_attachment("bundle.zip", "application", "zip", buffer.getvalue())

    parsed = parse_email(raw)

    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].is_password_protected is False


def test_non_zip_attachment_reports_undetectable_password_protection() -> None:
    """Edge case: protection can't be determined for non-ZIP formats (e.g. a
    PDF), so it must report None rather than guessing either way."""
    parsed = parse_email(_load("legitimate.eml"))

    assert parsed.attachments[0].is_password_protected is None


def test_email_exceeding_max_bytes_is_rejected_before_parsing() -> None:
    """Bounds total input size so header/body/attachment extraction never
    has to operate on an unbounded amount of decoded data."""
    raw = _load("legitimate.eml")

    with pytest.raises(EmailParsingError):
        parse_email(raw, max_bytes=10)
