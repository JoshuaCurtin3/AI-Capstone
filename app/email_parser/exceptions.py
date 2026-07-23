"""Errors raised by app/email_parser.

Subclasses app.core.exceptions.AppError so callers can catch parsing
failures specifically without catching unrelated application errors.
"""

from __future__ import annotations

from app.core.exceptions import AppError


class EmailParsingError(AppError):
    """Raised when a raw email cannot be safely parsed (too large, corrupt, ...)."""
