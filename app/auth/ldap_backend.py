"""LDAPS authentication against Active Directory.

Per CLAUDE.md: this is the *only* place a login password is ever handled,
and it is never compared locally - the actual credential check is always a
bind-as-user against the directory itself. No password or LDAP credential
is ever logged.

Nested group membership is resolved client-side (a breadth-first walk over
each group's own `memberOf` attribute) rather than via Active Directory's
server-side `LDAP_MATCHING_RULE_IN_CHAIN` extension. That OID-based filter
isn't implemented by `ldap3`'s mock test strategy, so relying on it would
ship an authorization-critical code path with no unit-test coverage - see
docs/architecture.md's Phase 6 section for the full rationale.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import NamedTuple

import ldap3
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from app.auth.schemas import AuthenticatedUser
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_USER_ATTRIBUTES = ["displayName", "mail", "memberOf"]
_GROUP_ATTRIBUTES = ["memberOf"]


class _FoundUser(NamedTuple):
    dn: str
    display_name: str
    email: str | None
    direct_groups: list[str]


def _build_server(settings: Settings) -> ldap3.Server:
    """Build the LDAPS server handle. `use_ssl=True` is explicit (not just
    inferred from the ldaps:// URI) as a second, code-level guarantee that
    this never falls back to plaintext LDAP.
    """
    return ldap3.Server(
        settings.ldap_server_uri,
        use_ssl=True,
        connect_timeout=settings.ldap_connect_timeout_seconds,
    )


def _connect(server: ldap3.Server, user: str, password: str) -> ldap3.Connection:
    """Build a not-yet-bound connection. The sole seam tests monkeypatch to
    substitute a MOCK_SYNC connection sharing a fake in-memory directory,
    so the rest of this module never has to know it's being tested.
    """
    return ldap3.Connection(server, user=user, password=password, auto_bind=False)


def _find_user(
    connection: ldap3.Connection, settings: Settings, username: str
) -> _FoundUser | None:
    """Search for `username` under the configured base DN. Returns None if
    no matching entry exists - the caller treats that identically to a
    wrong password, so this alone never lets an attacker enumerate users.
    """
    safe_username = escape_filter_chars(username)
    search_filter = f"({settings.ldap_user_login_attribute}={safe_username})"
    found = connection.search(
        settings.ldap_user_search_base_dn,
        search_filter,
        search_scope=ldap3.SUBTREE,
        attributes=_USER_ATTRIBUTES,
    )
    if not found or not connection.entries:
        return None

    entry = connection.entries[0]
    direct_groups = (
        [str(value) for value in entry["memberOf"].values] if "memberOf" in entry else []
    )
    display_name = (
        str(entry["displayName"].value)
        if "displayName" in entry and entry["displayName"].value
        else username
    )
    email = str(entry["mail"].value) if "mail" in entry and entry["mail"].value else None
    return _FoundUser(
        dn=entry.entry_dn, display_name=display_name, email=email, direct_groups=direct_groups
    )


def _resolve_group_membership(
    connection: ldap3.Connection,
    direct_group_dns: list[str],
    target_group_dn: str,
    *,
    max_depth: int,
) -> bool:
    """True if `target_group_dn` is reachable from `direct_group_dns` by
    walking parent-group `memberOf` attributes (direct OR nested
    membership). Visited-DN tracking plus `max_depth` guard against a
    cyclic or unexpectedly deep group graph.
    """
    target_normalized = target_group_dn.strip().lower()
    visited: set[str] = set()
    frontier = list(direct_group_dns)

    for _ in range(max_depth):
        if not frontier:
            break
        next_frontier: list[str] = []
        for group_dn in frontier:
            normalized = group_dn.strip().lower()
            if normalized in visited:
                continue
            visited.add(normalized)
            if normalized == target_normalized:
                return True
            found = connection.search(
                group_dn,
                "(objectClass=*)",
                search_scope=ldap3.BASE,
                attributes=_GROUP_ATTRIBUTES,
            )
            if found and connection.entries:
                entry = connection.entries[0]
                if "memberOf" in entry:
                    next_frontier.extend(str(value) for value in entry["memberOf"].values)
        frontier = next_frontier

    return False


def _authenticate_via_directory(
    server: ldap3.Server, settings: Settings, username: str, password: str
) -> AuthenticatedUser | None:
    service_conn = _connect(server, settings.ldap_bind_dn, settings.ldap_bind_password)
    if not service_conn.bind():
        logger.error(
            "LDAP service account bind failed - check APP_LDAP_BIND_DN/APP_LDAP_BIND_PASSWORD"
        )
        return None

    try:
        found_user = _find_user(service_conn, settings, username)
        if found_user is None:
            return None  # no such user - generic failure, no enumeration

        user_conn = _connect(server, found_user.dn, password)
        try:
            if not user_conn.bind():
                return None  # wrong password
        finally:
            user_conn.unbind()

        is_in_required_group = _resolve_group_membership(
            service_conn,
            found_user.direct_groups,
            settings.ldap_required_group_dn,
            max_depth=settings.ldap_group_membership_max_depth,
        )
    finally:
        service_conn.unbind()

    return AuthenticatedUser(
        username=username,
        display_name=found_user.display_name,
        email=found_user.email,
        groups=found_user.direct_groups,
        is_in_required_group=is_in_required_group,
        authenticated_at=datetime.now(UTC),
    )


def authenticate(
    username: str, password: str, *, settings: Settings | None = None
) -> AuthenticatedUser | None:
    """Authenticate `username`/`password` against Active Directory over LDAPS.

    Returns None for *any* failure - unknown user, wrong password, or an
    LDAP/network error - so callers can never distinguish "no such user"
    from "wrong password" (avoids username enumeration). A returned user's
    `is_in_required_group` still needs to be checked by the caller; this
    function itself never gates on it, since the password is validated
    first regardless of authorization.
    """
    settings = settings or get_settings()
    server = _build_server(settings)
    try:
        return _authenticate_via_directory(server, settings, username, password)
    except LDAPException:
        logger.exception("LDAP error while authenticating user")
        return None
