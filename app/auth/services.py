"""Persistence for the local User cache (app/auth/models.py::User).

Upserts a local row from an already-authenticated AuthenticatedUser -
never a password or any other credential. AD via LDAPS remains the sole
source of truth for identity and authorization; this is a read-mostly
local cache/reference so other domains (phishing_detection's
AnalysisResult) can attribute an action to a user.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.schemas import AuthenticatedUser


def get_or_create_user(db: Session, authenticated_user: AuthenticatedUser) -> User:
    """Find or create the local User row for `authenticated_user`, keeping
    display_name/email in sync with the latest AD data on every call.

    Does not commit - callers control the transaction boundary (see
    app/auth/router.py and app/api/v1/upload.py).
    """
    user = db.execute(
        select(User).where(User.username == authenticated_user.username)
    ).scalar_one_or_none()
    if user is None:
        user = User(username=authenticated_user.username)
        db.add(user)
    user.display_name = authenticated_user.display_name
    user.email = authenticated_user.email
    db.flush()  # populate user.id (and bump updated_at) without a full commit
    return user
