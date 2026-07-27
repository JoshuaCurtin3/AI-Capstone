"""Unit tests for app.phishing_detection.rules.attachment_analysis."""

from __future__ import annotations

from app.email_parser.schemas import AttachmentMeta, ParsedEmail
from app.phishing_detection.rules.attachment_analysis import check_attachments


def _attachment(filename: str | None, is_password_protected: bool | None = None) -> AttachmentMeta:
    return AttachmentMeta(
        filename=filename,
        content_type="application/octet-stream",
        size_bytes=10,
        sha256="0" * 64,
        is_password_protected=is_password_protected,
    )


def _rule_ids(attachments: list[AttachmentMeta]) -> set[str]:
    return {f.rule_id for f in check_attachments(ParsedEmail(attachments=attachments))}


# --- Executable extensions ---


def test_executable_extension_triggers_finding() -> None:
    assert "ATT-EXECUTABLE" in _rule_ids([_attachment("update.exe")])


def test_document_extension_does_not_trigger_executable_rule() -> None:
    assert "ATT-EXECUTABLE" not in _rule_ids([_attachment("report.pdf")])


def test_unnamed_attachment_does_not_crash_or_trigger() -> None:
    """Edge case: a part with no filename at all must be skipped safely."""
    assert _rule_ids([_attachment(None)]) == set()


# --- Double extensions ---


def test_double_extension_disguising_executable_triggers_finding() -> None:
    assert "ATT-DOUBLE-EXTENSION" in _rule_ids([_attachment("invoice.pdf.exe")])


def test_single_extension_does_not_trigger_double_extension_rule() -> None:
    assert "ATT-DOUBLE-EXTENSION" not in _rule_ids([_attachment("invoice.pdf")])


def test_double_extension_without_executable_suffix_does_not_trigger() -> None:
    """Edge case: two extensions where the final one isn't executable
    (e.g. a tarball name like archive.tar.gz) isn't a disguise attempt."""
    assert "ATT-DOUBLE-EXTENSION" not in _rule_ids([_attachment("archive.tar.gz")])


# --- Macro-enabled Office files ---


def test_macro_enabled_docm_triggers_finding() -> None:
    assert "ATT-MACRO-ENABLED" in _rule_ids([_attachment("resume.docm")])


def test_plain_docx_does_not_trigger_macro_rule() -> None:
    assert "ATT-MACRO-ENABLED" not in _rule_ids([_attachment("resume.docx")])


# --- Password-protected archives ---


def test_password_protected_archive_triggers_finding() -> None:
    assert "ATT-PASSWORD-PROTECTED-ARCHIVE" in _rule_ids(
        [_attachment("secret.zip", is_password_protected=True)]
    )


def test_non_protected_archive_does_not_trigger_password_rule() -> None:
    assert "ATT-PASSWORD-PROTECTED-ARCHIVE" not in _rule_ids(
        [_attachment("public.zip", is_password_protected=False)]
    )


def test_undetectable_protection_does_not_trigger() -> None:
    """Edge case: is_password_protected=None (not a readable ZIP) must not
    be treated as a positive detection."""
    assert "ATT-PASSWORD-PROTECTED-ARCHIVE" not in _rule_ids(
        [_attachment("mystery.rar", is_password_protected=None)]
    )


# --- Archive attachments ---


def test_archive_attachment_triggers_finding() -> None:
    assert "ATT-ARCHIVE" in _rule_ids([_attachment("bundle.zip")])


def test_non_archive_attachment_does_not_trigger_archive_rule() -> None:
    assert "ATT-ARCHIVE" not in _rule_ids([_attachment("report.pdf")])


def test_no_attachments_produces_no_findings() -> None:
    assert check_attachments(ParsedEmail(attachments=[])) == []
