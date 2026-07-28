"""Signed session cookie handling.

A custom signed cookie (via itsdangerous) rather than Starlette's built-in
SessionMiddleware, so the exact cookie flags (HttpOnly/Secure/SameSite) and
expiry are fully controlled here in one place - see docs/architecture.md's
Phase 6 section. Signed with the app's existing Settings.secret_key, so no
new secret needs to be provisioned.
"""

from __future__ import annotations

from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.auth.schemas import AuthenticatedUser
from app.config import Settings, get_settings

SESSION_COOKIE_NAME = "session"
#: Distinct salt so a session token can never be replayed as a CSRF token
#: (or any other itsdangerous-signed value) even though they may share a key.
_SESSION_SALT = "auth-session-v1"


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt=_SESSION_SALT)


def create_session_cookie(
    response: Response, user: AuthenticatedUser, *, settings: Settings | None = None
) -> None:
    """Sign `user` and attach it to `response` as the session cookie."""
    settings = settings or get_settings()
    token = _serializer(settings).dumps(user.model_dump(mode="json"))
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )


def read_session(request: Request, *, settings: Settings | None = None) -> AuthenticatedUser | None:
    """Return the authenticated user for this request, or None if there is
    no session cookie, it's missing/tampered/unsigned, or it has expired.
    Never raises - a bad cookie is treated exactly like no cookie at all.
    """
    settings = settings or get_settings()
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        return None
    try:
        payload = _serializer(settings).loads(raw_token, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return AuthenticatedUser.model_validate(payload)
    except ValueError:
        # Cookie was validly signed but no longer matches the current
        # AuthenticatedUser shape (e.g. after a field rename) - treat as
        # logged out rather than raising into the request path.
        return None


def clear_session_cookie(response: Response) -> None:
    """Remove the session cookie (used by logout)."""
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
