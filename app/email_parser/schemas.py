"""Structured data produced by app/email_parser/parser.py.

These are plain Pydantic models - the contract between email parsing and
every downstream consumer (phishing_detection's scoring engine, ai_analysis's
explanation generation, and the upload template). Keeping them independent of
SQLAlchemy lets the scoring engine be tested against plain data, no DB needed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ParsedURL(BaseModel):
    """A URL found in a message body."""

    url: str
    display_text: str | None = None
    source: Literal["text", "html"]
    #: True when the visible link text looks like a different destination
    #: than the actual href target - a common phishing technique.
    is_obfuscated: bool = False


class AttachmentMeta(BaseModel):
    """Metadata about an attachment - never its raw content.

    The parser hashes/sizes attachment bytes in memory to populate this but
    never writes, opens, or executes the payload (CLAUDE.md / TASKS.md
    Phase 3 "safe parsing" requirement).
    """

    filename: str | None = None
    content_type: str
    size_bytes: int
    sha256: str
    #: True/False when the attachment is a ZIP whose local file headers carry
    #: the encryption flag; None when the format isn't a ZIP or couldn't be
    #: read as one, since encryption can't be determined without opening it
    #: (Phase 4 attachment rule "password-protected archive (if detectable)").
    is_password_protected: bool | None = None


class ParsedEmail(BaseModel):
    """Structured representation of a raw email message."""

    subject: str | None = None
    from_address: str | None = None
    to_addresses: list[str] = []
    date: str | None = None
    reply_to: str | None = None
    return_path: str | None = None
    message_id: str | None = None
    authentication_results: list[str] = []
    received_headers: list[str] = []
    text_body: str | None = None
    html_body: str | None = None
    urls: list[ParsedURL] = []
    attachments: list[AttachmentMeta] = []
