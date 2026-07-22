"""Business logic: turn a raw email (e.g. .eml bytes) into structured data.

TODO: implement parsing (headers, sender/reply-to, body text/HTML, links,
attachments) and return the schema defined in schemas.py. This module must
only parse/normalize — no risk scoring happens here (see phishing_detection).
"""

from __future__ import annotations


def parse_email(raw_email: bytes) -> None:
    raise NotImplementedError
