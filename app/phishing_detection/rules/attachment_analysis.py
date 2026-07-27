"""Attachment-based detection rules: executable/double extensions,
macro-enabled Office files, password-protected archives, and archives in
general.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from app.email_parser.schemas import AttachmentMeta, ParsedEmail
from app.phishing_detection.schemas import Finding

_EXECUTABLE_EXTENSIONS = {
    ".exe",
    ".scr",
    ".bat",
    ".cmd",
    ".com",
    ".pif",
    ".vbs",
    ".vbe",
    ".js",
    ".jse",
    ".jar",
    ".msi",
    ".ps1",
    ".wsf",
    ".gadget",
    ".hta",
}

_MACRO_EXTENSIONS = {".docm", ".xlsm", ".pptm", ".dotm", ".xltm", ".potm"}

_ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2"}

#: Extensions commonly used as the "disguise" half of a double extension,
#: e.g. invoice.pdf.exe.
_COMMON_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
}


def _suffixes(filename: str) -> list[str]:
    return PurePosixPath(filename.lower()).suffixes


def _filenames_with_final_suffix_in(
    attachments: list[AttachmentMeta], extensions: set[str]
) -> list[str]:
    matches: list[str] = []
    for attachment in attachments:
        if not attachment.filename:
            continue
        suffixes = _suffixes(attachment.filename)
        if suffixes and suffixes[-1] in extensions:
            matches.append(attachment.filename)
    return matches


def _check_executable(attachments: list[AttachmentMeta]) -> list[Finding]:
    matches = _filenames_with_final_suffix_in(attachments, _EXECUTABLE_EXTENSIONS)
    if not matches:
        return []
    return [
        Finding(
            rule_id="ATT-EXECUTABLE",
            category="attachment",
            name="Executable attachment",
            points=20,
            evidence=", ".join(matches),
            explanation=(
                "Executable file types can run arbitrary code on the recipient's "
                "machine and are rarely sent as legitimate attachments."
            ),
        )
    ]


def _check_double_extension(attachments: list[AttachmentMeta]) -> list[Finding]:
    matches: list[str] = []
    for attachment in attachments:
        if not attachment.filename:
            continue
        suffixes = _suffixes(attachment.filename)
        if (
            len(suffixes) >= 2
            and suffixes[-2] in _COMMON_DOCUMENT_EXTENSIONS
            and suffixes[-1] in _EXECUTABLE_EXTENSIONS
        ):
            matches.append(attachment.filename)
    if not matches:
        return []
    return [
        Finding(
            rule_id="ATT-DOUBLE-EXTENSION",
            category="attachment",
            name="Double file extension",
            points=15,
            evidence=", ".join(matches),
            explanation=(
                "The filename disguises an executable behind what looks like a "
                "document extension (e.g. invoice.pdf.exe), a common trick to "
                "bypass casual inspection."
            ),
        )
    ]


def _check_macro_enabled(attachments: list[AttachmentMeta]) -> list[Finding]:
    matches = _filenames_with_final_suffix_in(attachments, _MACRO_EXTENSIONS)
    if not matches:
        return []
    return [
        Finding(
            rule_id="ATT-MACRO-ENABLED",
            category="attachment",
            name="Macro-enabled Office file",
            points=15,
            evidence=", ".join(matches),
            explanation=(
                "Macro-enabled Office documents can execute embedded code when "
                "opened and are a common malware delivery method."
            ),
        )
    ]


def _check_password_protected(attachments: list[AttachmentMeta]) -> list[Finding]:
    matches = [
        attachment.filename or "(unnamed)"
        for attachment in attachments
        if attachment.is_password_protected
    ]
    if not matches:
        return []
    return [
        Finding(
            rule_id="ATT-PASSWORD-PROTECTED-ARCHIVE",
            category="attachment",
            name="Password-protected archive",
            points=10,
            evidence=", ".join(matches),
            explanation=(
                "Password-protected archives prevent automated content/malware "
                "scanning and are frequently used to smuggle malicious payloads "
                "past email security filters."
            ),
        )
    ]


def _check_archive(attachments: list[AttachmentMeta]) -> list[Finding]:
    matches = _filenames_with_final_suffix_in(attachments, _ARCHIVE_EXTENSIONS)
    if not matches:
        return []
    return [
        Finding(
            rule_id="ATT-ARCHIVE",
            category="attachment",
            name="Archive attachment",
            points=5,
            evidence=", ".join(matches),
            explanation=(
                "Archive attachments can conceal the file types inside them from "
                "a casual look at the message."
            ),
        )
    ]


def check_attachments(parsed_email: ParsedEmail) -> list[Finding]:
    """Run every attachment-based rule and return all triggered findings."""
    attachments = parsed_email.attachments
    findings: list[Finding] = []
    findings.extend(_check_executable(attachments))
    findings.extend(_check_double_extension(attachments))
    findings.extend(_check_macro_enabled(attachments))
    findings.extend(_check_password_protected(attachments))
    findings.extend(_check_archive(attachments))
    return findings
