"""Errors raised by app/auth.

Subclasses app.core.exceptions.AppError so callers can catch auth failures
specifically without catching unrelated application errors.
"""

from __future__ import annotations

from app.core.exceptions import AppError


class AuthenticationRequiredError(AppError):
    """Raised by app.auth.dependencies.require_user when there is no valid
    session. Caught by a handler in app/main.py that redirects to
    /login?next=<next_path>, preserving the page the user was trying to reach.
    """

    def __init__(self, next_path: str) -> None:
        self.next_path = next_path
        super().__init__(f"Authentication required to access {next_path!r}")
