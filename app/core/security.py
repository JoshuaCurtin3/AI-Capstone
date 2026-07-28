"""CSRF protection helper (double-submit cookie pattern).

FastAPI has no built-in CSRF protection, unlike Django - see CLAUDE.md's
"secure defaults" requirement and docs/architecture.md's framework-pivot
notes. This is a generic primitive (not auth-domain-specific), so it lives
in app/core rather than app/auth, ready for any future session-authenticated
POST form to reuse.

Double-submit cookie: an unpredictable token is set as a cookie and also
embedded in the rendered form as a hidden field. On submit, the two must
match. This needs no server-side token store, which matters here since
there is no session established yet at the point /login itself is
submitted (and no database at all before Phase 5).
"""

from __future__ import annotations

import secrets

from fastapi import Request

CSRF_COOKIE_NAME = "csrf_token"
CSRF_COOKIE_MAX_AGE_SECONDS = 3600


def generate_csrf_token() -> str:
    """A fresh, unpredictable token for a new CSRF cookie."""
    return secrets.token_urlsafe(32)


def verify_csrf_token(request: Request, submitted_token: str | None) -> bool:
    """True only if `submitted_token` (from a form field) matches the
    token in the request's own CSRF cookie. Constant-time comparison to
    avoid leaking the token via response-timing side channels.
    """
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_token or not submitted_token:
        return False
    return secrets.compare_digest(cookie_token, submitted_token)
