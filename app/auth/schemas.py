"""Structured data produced by app/auth - the contract between the LDAP
backend, the session cookie, and every route/template that needs to know
who (if anyone) is logged in.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """A user successfully authenticated against Active Directory.

    Never carries a password or any LDAP credential - only what's needed to
    render the UI and gate access. `is_in_required_group` reflects direct
    OR nested membership in `Settings.ldap_required_group_dn` (see
    app/auth/ldap_backend.py) at the moment of login; it is not re-checked
    on every request.
    """

    username: str
    display_name: str
    email: str | None = None
    groups: list[str] = []
    is_in_required_group: bool
    authenticated_at: datetime
