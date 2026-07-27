"""Upload endpoint: accept a pasted raw email or an .eml file upload, parse
it into structured data, and render the result.

Never executes attachment payloads and never fetches any extracted URL -
see app/email_parser/parser.py for the parsing rules that guarantee this.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse

from app.config import Settings, get_settings
from app.core.templates import templates
from app.email_parser.exceptions import EmailParsingError
from app.email_parser.parser import parse_email
from app.email_parser.schemas import ParsedEmail
from app.phishing_detection.schemas import ScoringResult
from app.phishing_detection.scoring_engine import calculate_risk_score

router = APIRouter()
logger = logging.getLogger(__name__)

#: Browsers send inconsistent (or no) Content-Type for .eml uploads since
#: message/rfc822 isn't a registered browser MIME type - accept the common
#: values rather than rejecting legitimate uploads on that alone.
ALLOWED_UPLOAD_CONTENT_TYPES = {"", "message/rfc822", "application/octet-stream", "text/plain"}


@router.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request) -> HTMLResponse:
    """Render the paste/upload form."""
    return templates.TemplateResponse(request, "upload.html", {})


@router.post("/upload", response_class=HTMLResponse)
async def upload_submit(
    request: Request,
    raw_email_text: str = Form(default=""),
    file: UploadFile | None = File(default=None),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    """Parse a pasted raw email or an uploaded .eml file and render it."""
    error: str | None = None
    raw_bytes: bytes | None = None

    if file is not None and file.filename:
        if not file.filename.lower().endswith(".eml"):
            error = "Only .eml files are accepted."
        elif file.content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
            error = f"Unsupported upload content type: {file.content_type!r}."
        else:
            # Read at most one byte past the limit so we can detect and
            # reject an oversized upload without buffering the whole file.
            raw_bytes = await file.read(settings.max_email_upload_bytes + 1)
            if len(raw_bytes) > settings.max_email_upload_bytes:
                error = "Uploaded file exceeds the maximum allowed size."
                raw_bytes = None
    elif raw_email_text.strip():
        raw_bytes = raw_email_text.encode("utf-8", errors="replace")
        if len(raw_bytes) > settings.max_email_upload_bytes:
            error = "Pasted email exceeds the maximum allowed size."
            raw_bytes = None
    else:
        error = "Paste a raw email or choose an .eml file to upload."

    parsed: ParsedEmail | None = None
    scoring: ScoringResult | None = None
    if raw_bytes is not None and error is None:
        try:
            parsed = parse_email(raw_bytes, max_bytes=settings.max_email_upload_bytes)
            # Scoring runs immediately after parsing and before any AI
            # involvement - the risk score is deterministic output of
            # phishing_detection alone (see CLAUDE.md's core rule).
            scoring = calculate_risk_score(parsed)
        except EmailParsingError as exc:
            logger.warning("Failed to parse submitted email: %s", exc)
            error = str(exc)

    return templates.TemplateResponse(
        request, "upload.html", {"parsed": parsed, "scoring": scoring, "error": error}
    )
