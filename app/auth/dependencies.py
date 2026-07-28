"""FastAPI dependencies for reading/requiring the current user.

`AuthContextMiddleware` already resolves `request.state.user` on every
request; these dependencies just give route handlers a typed way to depend
on that, without re-parsing the session cookie.
"""

from __future__ import annotations

from fastapi import Request

from app.auth.exceptions import AuthenticationRequiredError
from app.auth.schemas import AuthenticatedUser


def get_current_user(request: Request) -> AuthenticatedUser | None:
    """The logged-in user, or None - for routes/templates where auth is
    optional (e.g. the navbar showing Login vs. a logged-in username).
    """
    user: AuthenticatedUser | None = getattr(request.state, "user", None)
    return user


def require_user(request: Request) -> AuthenticatedUser:
    """The logged-in user, or raise AuthenticationRequiredError.

    A handler registered in app/main.py turns that into a redirect to
    /login?next=<the page the user was trying to reach> - see
    app/auth/exceptions.py.
    """
    user = get_current_user(request)
    if user is None:
        next_path = request.url.path
        if request.url.query:
            next_path = f"{next_path}?{request.url.query}"
        raise AuthenticationRequiredError(next_path)
    return user
