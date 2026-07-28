"""Login/logout routes plus a minimal protected page (/account) that
demonstrates require_user - see TASKS.md Phase 6.

/upload is intentionally left ungated in this phase; /account exists so
route protection has a real, working example to test against.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import ldap_backend, session
from app.auth.dependencies import get_current_user, require_user
from app.auth.schemas import AuthenticatedUser
from app.auth.services import get_or_create_user
from app.core.security import verify_csrf_token
from app.core.templates import templates
from app.database.session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


def _safe_next_path(value: str | None) -> str:
    """Only allow same-site relative paths as a post-login redirect target,
    to prevent an open redirect via a crafted ?next= value.
    """
    if not value or not value.startswith("/") or value.startswith("//") or "://" in value:
        return "/"
    return value


def _render_login(
    request: Request, *, next_path: str, error: str | None = None, status_code: int = 200
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "login.html",
        {"next": next_path, "error": error},
        status_code=status_code,
    )


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str | None = None) -> Response:
    """Render the login form, or bounce an already-logged-in user onward."""
    safe_next = _safe_next_path(next)
    if get_current_user(request) is not None:
        return RedirectResponse(safe_next, status_code=303)
    return _render_login(request, next_path=safe_next)


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    next: str = Form(default="/"),
    db: Session = Depends(get_db),
) -> Response:
    """Validate CSRF, authenticate against AD, and start a session."""
    safe_next = _safe_next_path(next)

    if not verify_csrf_token(request, csrf_token):
        logger.warning("Login rejected: invalid or missing CSRF token")
        return _render_login(
            request,
            next_path=safe_next,
            error="Invalid or expired form submission. Please try again.",
            status_code=403,
        )

    user: AuthenticatedUser | None = ldap_backend.authenticate(username, password)
    if user is None:
        return _render_login(
            request,
            next_path=safe_next,
            error="Invalid username or password.",
            status_code=401,
        )

    if not user.is_in_required_group:
        logger.warning("Login rejected for %r: not a member of the required AD group", username)
        return _render_login(
            request,
            next_path=safe_next,
            error="Your account is not authorized to use this application.",
            status_code=403,
        )

    # Best-effort (Phase 5): cache a local User row for this AD identity so
    # phishing_detection's AnalysisResult can reference who submitted an
    # analysis. Never blocks login - AD via LDAPS is still the sole source
    # of truth for identity/authorization even if this write fails.
    try:
        get_or_create_user(db, user)
        db.commit()
    except SQLAlchemyError:
        logger.exception("Failed to cache local user record - continuing without it")
        db.rollback()

    response = RedirectResponse(safe_next, status_code=303)
    session.create_session_cookie(response, user)
    return response


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)) -> RedirectResponse:
    """Clear the session cookie. CSRF-protected like the login form, per
    TASKS.md Phase 6, even though the worst case of a forged logout is a
    nuisance rather than a compromise.
    """
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token.")

    response = RedirectResponse("/", status_code=303)
    session.clear_session_cookie(response)
    return response


@router.get("/account", response_class=HTMLResponse)
def account(
    request: Request, current_user: AuthenticatedUser = Depends(require_user)
) -> HTMLResponse:
    """A minimal protected page: demonstrates require_user end-to-end."""
    return templates.TemplateResponse(request, "account.html", {"current_user": current_user})
