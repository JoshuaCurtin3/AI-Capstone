"""Analysis history dashboard for the logged-in user (Phase 5).

Gated behind require_user - an analysis history is only meaningful once
there's a known identity to filter by, and /upload itself remains public
(Phase 6 decision) so anonymous submissions simply never appear here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_user
from app.auth.models import User
from app.auth.schemas import AuthenticatedUser
from app.core.templates import templates
from app.database.session import get_db
from app.phishing_detection.models import AnalysisResult

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Show the logged-in user's own analysis history, newest first."""
    results = (
        db.execute(
            select(AnalysisResult)
            .join(AnalysisResult.submitted_by)
            .where(User.username == current_user.username)
            .order_by(AnalysisResult.created_at.desc())
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(request, "dashboard.html", {"results": results})
