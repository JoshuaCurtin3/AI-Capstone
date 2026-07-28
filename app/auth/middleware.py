"""Per-request auth context.

Resolves the current user (if any) and ensures a CSRF cookie exists on
every request, stashing both on `request.state` so templates (base.html's
navbar, login.html's form) and route handlers can read them without every
route threading them through its own context dict by hand.

This is auth-domain logic, so it lives here under app/auth rather than in
the still-empty app/core/middleware.py stub - see
docs/architecture.md: "domain-specific code lives in its domain package."
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.auth.schemas import AuthenticatedUser
from app.auth.session import read_session
from app.config import get_settings
from app.core.security import CSRF_COOKIE_MAX_AGE_SECONDS, CSRF_COOKIE_NAME, generate_csrf_token


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        user: AuthenticatedUser | None = read_session(request)
        request.state.user = user

        existing_csrf_token = request.cookies.get(CSRF_COOKIE_NAME)
        csrf_token = existing_csrf_token or generate_csrf_token()
        request.state.csrf_token = csrf_token

        response = await call_next(request)

        if not existing_csrf_token:
            settings = get_settings()
            response.set_cookie(
                CSRF_COOKIE_NAME,
                csrf_token,
                max_age=CSRF_COOKIE_MAX_AGE_SECONDS,
                httponly=True,
                secure=settings.environment == "production",
                samesite="lax",
                path="/",
            )

        return response
