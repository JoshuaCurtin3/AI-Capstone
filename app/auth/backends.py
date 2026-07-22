"""Custom Django authentication backend: Active Directory over LDAPS.

TODO: implement using django-auth-ldap's LDAPBackend, configured with the
LDAP_* environment variables (see .env.example). This backend must only
authenticate/authorize users — it must never be involved in phishing risk
scoring (see CLAUDE.md).
"""

from __future__ import annotations

from django.contrib.auth.models import User


class LDAPBackend:
    """Authenticates users against Active Directory via LDAPS."""

    def authenticate(
        self, request: object, username: str | None = None, password: str | None = None
    ) -> User | None:
        raise NotImplementedError

    def get_user(self, user_id: int) -> User | None:
        raise NotImplementedError
