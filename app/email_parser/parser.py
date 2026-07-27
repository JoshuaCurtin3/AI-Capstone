"""Safely parse a raw email (pasted text or .eml upload) into structured data.

Safety guarantees (CLAUDE.md / TASKS.md Phase 3 "safe parsing"):

- Never executes attachment payloads - attachments are only hashed/sized,
  never written to disk or opened.
- Never fetches/visits any extracted URL - URLs are recognized by regex and
  HTML-tag inspection only, never dereferenced.
- Never raises an uncaught exception for malformed input - any failure this
  module can't recover from is reported as the typed EmailParsingError, and
  per-section failures (a single unreadable body or attachment part) degrade
  gracefully instead of aborting the whole parse.
- The raw input size is bounded up front, so header/body/attachment
  extraction below never has to operate on an unbounded amount of data.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import zipfile
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from app.email_parser.exceptions import EmailParsingError
from app.email_parser.schemas import AttachmentMeta, ParsedEmail, ParsedURL

logger = logging.getLogger(__name__)

#: Default cap on raw email size accepted by parse_email(); callers (e.g. the
#: upload endpoint) may pass a stricter, configured limit.
DEFAULT_MAX_BYTES = 10_000_000  # 10 MB

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
#: Trailing characters that are almost always sentence punctuation rather
#: than part of the URL itself (e.g. "...at https://example.com/x.").
_TRAILING_PUNCTUATION = ".,;:!?)'\""
_DOMAIN_LIKE_RE = re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)+\b", re.IGNORECASE)

_ZIP_CONTENT_TYPES = {"application/zip", "application/x-zip-compressed"}


def parse_email(raw_email: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES) -> ParsedEmail:
    """Parse raw .eml bytes into a ParsedEmail.

    Raises EmailParsingError (never an uncaught exception) if the input is
    oversized or cannot be safely parsed.
    """
    if len(raw_email) > max_bytes:
        raise EmailParsingError(
            f"Email is {len(raw_email)} bytes, exceeding the {max_bytes}-byte limit."
        )

    try:
        message = BytesParser(EmailMessage, policy=policy.default).parsebytes(raw_email)
    except Exception as exc:  # pragma: no cover - stdlib parser is extremely lenient
        raise EmailParsingError(f"Could not parse email: {exc}") from exc

    try:
        text_body = _get_body(message, "plain")
        html_body = _get_body(message, "html")
        return ParsedEmail(
            subject=_header(message, "Subject"),
            from_address=_header(message, "From"),
            to_addresses=_address_list(message, "To"),
            date=_header(message, "Date"),
            reply_to=_header(message, "Reply-To"),
            return_path=_header(message, "Return-Path"),
            message_id=_header(message, "Message-ID"),
            authentication_results=_header_list(message, "Authentication-Results"),
            received_headers=_header_list(message, "Received"),
            text_body=text_body,
            html_body=html_body,
            urls=_extract_urls(text_body, html_body),
            attachments=_extract_attachments(message),
        )
    except EmailParsingError:
        raise
    except Exception as exc:
        # Any unexpected failure past this point becomes a clean, typed error
        # instead of an uncaught traceback - see module docstring.
        raise EmailParsingError(f"Could not parse email: {exc}") from exc


def _header(message: EmailMessage, name: str) -> str | None:
    value = message.get(name)
    return str(value) if value is not None else None


def _header_list(message: EmailMessage, name: str) -> list[str]:
    return [str(value) for value in message.get_all(name, failobj=[])]


def _address_list(message: EmailMessage, name: str) -> list[str]:
    raw_values = [str(value) for value in message.get_all(name, failobj=[])]
    return [
        f"{display_name} <{addr}>" if display_name else addr
        for display_name, addr in getaddresses(raw_values)
        if addr
    ]


def _get_body(message: EmailMessage, subtype: str) -> str | None:
    try:
        part = message.get_body(preferencelist=(subtype,))
    except Exception as exc:
        logger.warning("Failed to locate %s body part: %s", subtype, exc)
        return None
    if part is None:
        return None
    try:
        content = part.get_content()
    except Exception as exc:
        logger.warning("Failed to decode %s body, falling back to raw bytes: %s", subtype, exc)
        payload = part.get_payload(decode=True)
        content = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else None
    return content if isinstance(content, str) else None


def _detect_zip_password_protection(payload: bytes) -> bool | None:
    """True/False if the ZIP's own local file headers flag encryption.

    Reads only the ZIP central directory metadata (same trust level as the
    sha256 hash already computed) - never extracts/opens a member's content,
    so this stays consistent with the "never execute attachment payloads"
    safety guarantee above. Returns None when the bytes aren't a readable
    ZIP at all, since protection can't be determined in that case.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            return any(info.flag_bits & 0x1 for info in archive.infolist())
    except (zipfile.BadZipFile, OSError):
        return None


def _extract_attachments(message: EmailMessage) -> list[AttachmentMeta]:
    """Return metadata for each attachment part - never its raw content."""
    attachments: list[AttachmentMeta] = []
    try:
        parts = list(message.iter_attachments())
    except Exception as exc:
        logger.warning("Failed to enumerate attachments: %s", exc)
        return attachments

    for part in parts:
        try:
            filename = part.get_filename()
            # Strip any path components a malicious sender embeds in the
            # filename - we only ever expose the basename, never a path.
            sanitized_filename = Path(filename).name if filename else None
            payload = part.get_payload(decode=True)
            payload_bytes = payload if isinstance(payload, bytes) else b""
            content_type = part.get_content_type()
            looks_like_zip = content_type in _ZIP_CONTENT_TYPES or (
                sanitized_filename is not None and sanitized_filename.lower().endswith(".zip")
            )
            attachments.append(
                AttachmentMeta(
                    filename=sanitized_filename,
                    content_type=content_type,
                    size_bytes=len(payload_bytes),
                    sha256=hashlib.sha256(payload_bytes).hexdigest(),
                    is_password_protected=(
                        _detect_zip_password_protection(payload_bytes) if looks_like_zip else None
                    ),
                )
            )
        except Exception as exc:
            logger.warning("Skipping unreadable attachment part: %s", exc)
            continue
    return attachments


class _AnchorExtractor(HTMLParser):
    """Collects (href, visible text) pairs from <a> tags.

    Uses the stdlib tokenizer only - never renders or executes the HTML and
    never follows any href (see module docstring).
    """

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._href = href
                self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._text).strip()))
            self._href = None
            self._text = []


def _hostname(value: str) -> str | None:
    parsed = urlparse(value if "//" in value else f"//{value}")
    host = parsed.hostname
    return host.removeprefix("www.") if host else None


def _looks_like_url(text: str) -> bool:
    return bool(_URL_RE.search(text) or _DOMAIN_LIKE_RE.search(text))


def _is_obfuscated(href: str, display_text: str) -> bool:
    """True when the visible link text names a different host than href.

    Classic phishing pattern: display text reads "https://yourbank.com/login"
    while the actual href points somewhere else entirely.
    """
    if not display_text or not _looks_like_url(display_text):
        return False
    display_host = _hostname(display_text)
    href_host = _hostname(href)
    return bool(display_host and href_host and display_host != href_host)


def _extract_urls(text_body: str | None, html_body: str | None) -> list[ParsedURL]:
    urls: list[ParsedURL] = []
    seen: set[tuple[str, str]] = set()

    if text_body:
        for match in _URL_RE.finditer(text_body):
            url = match.group(0).rstrip(_TRAILING_PUNCTUATION)
            key = (url, "text")
            if key not in seen:
                seen.add(key)
                urls.append(ParsedURL(url=url, source="text"))

    if html_body:
        extractor = _AnchorExtractor()
        try:
            extractor.feed(html_body)
        except Exception as exc:
            logger.warning("Failed to parse HTML body for links: %s", exc)

        for href, text in extractor.links:
            if not href.lower().startswith(("http://", "https://")):
                continue
            key = (href, "html")
            if key not in seen:
                seen.add(key)
                urls.append(
                    ParsedURL(
                        url=href,
                        display_text=text or None,
                        source="html",
                        is_obfuscated=_is_obfuscated(href, text),
                    )
                )

        for match in _URL_RE.finditer(html_body):
            url = match.group(0).rstrip(_TRAILING_PUNCTUATION)
            key = (url, "html")
            if key not in seen:
                seen.add(key)
                urls.append(ParsedURL(url=url, source="html"))

    return urls
