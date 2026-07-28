"""Unit tests for app.auth.ldap_backend.authenticate.

Everything here runs against ldap3's MOCK_SYNC in-memory directory - never a
live AD server, per CLAUDE.md ("tests mock LDAPS - never bind to real AD").
Production code opens two separate Connection objects (a service-account
bind for searching, then a bind-as-user with the submitted password); the
mock strategy gives each Connection its own isolated directory unless they
explicitly share the same `strategy.entries` dict, which _FakeDirectory
below sets up so the two connections behave like one real server.
"""

from __future__ import annotations

from typing import Any

import pytest
from ldap3 import MOCK_SYNC, Connection, Server

from app.auth import ldap_backend
from app.config import Settings

SERVICE_DN = "CN=svc-app,OU=Service Accounts,DC=example,DC=local"
SERVICE_PASSWORD = "svc-password"
USER_SEARCH_BASE = "OU=Users,DC=example,DC=local"
REQUIRED_GROUP_DN = "CN=Required,OU=Groups,DC=example,DC=local"

ALICE_DN = "CN=Alice Example,OU=Users,DC=example,DC=local"
ALICE_PASSWORD = "correct-horse"
DIRECT_GROUP_DN = "CN=TeamA,OU=Groups,DC=example,DC=local"


def _settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "secret_key": "test-secret-key",
        "ldap_server_uri": "ldaps://ad.example.local:636",
        "ldap_bind_dn": SERVICE_DN,
        "ldap_bind_password": SERVICE_PASSWORD,
        "ldap_user_search_base_dn": USER_SEARCH_BASE,
        "ldap_required_group_dn": REQUIRED_GROUP_DN,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class _FakeDirectory:
    """A shared in-memory LDAP directory that every mock Connection this
    test creates can see, so authenticate()'s two-connection flow behaves
    like it would against one real server.
    """

    def __init__(self, *, seed_service_account: bool = True) -> None:
        self.server = Server("fake-ad.example.local")
        self.entries: dict[str, Any] = {}
        if seed_service_account:
            self.add_entry(SERVICE_DN, {"userPassword": SERVICE_PASSWORD})

    def _connection(self, user: str, password: str) -> Connection:
        conn = Connection(
            self.server, user=user, password=password, client_strategy=MOCK_SYNC, auto_bind=False
        )
        conn.strategy.entries = self.entries
        return conn

    def add_entry(self, dn: str, attributes: dict[str, Any]) -> None:
        # Any bound-or-not connection can seed entries; strategy.entries is
        # the shared dict, so which connection object does it doesn't matter.
        seeder = self._connection("seed", "unused")
        seeder.strategy.add_entry(dn, attributes)

    def patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ldap_backend, "_build_server", lambda settings: self.server)
        monkeypatch.setattr(
            ldap_backend,
            "_connect",
            lambda server, user, password: self._connection(user, password),
        )


@pytest.fixture
def directory(monkeypatch: pytest.MonkeyPatch) -> _FakeDirectory:
    fake = _FakeDirectory()
    fake.patch(monkeypatch)
    return fake


def test_successful_login_with_direct_group_membership(directory: _FakeDirectory) -> None:
    directory.add_entry(REQUIRED_GROUP_DN, {"objectClass": "group"})
    directory.add_entry(
        ALICE_DN,
        {
            "sAMAccountName": "alice",
            "displayName": "Alice Example",
            "mail": "alice@example.local",
            "userPassword": ALICE_PASSWORD,
            "memberOf": [REQUIRED_GROUP_DN],
        },
    )

    user = ldap_backend.authenticate("alice", ALICE_PASSWORD, settings=_settings())

    assert user is not None
    assert user.username == "alice"
    assert user.display_name == "Alice Example"
    assert user.email == "alice@example.local"
    assert user.groups == [REQUIRED_GROUP_DN]
    assert user.is_in_required_group is True


def test_successful_login_with_nested_group_membership(directory: _FakeDirectory) -> None:
    """Alice is only directly a member of TeamA; TeamA is itself a member
    of the required group - nested membership must still authorize her.
    """
    directory.add_entry(REQUIRED_GROUP_DN, {"objectClass": "group"})
    directory.add_entry(DIRECT_GROUP_DN, {"objectClass": "group", "memberOf": [REQUIRED_GROUP_DN]})
    directory.add_entry(
        ALICE_DN,
        {
            "sAMAccountName": "alice",
            "displayName": "Alice Example",
            "userPassword": ALICE_PASSWORD,
            "memberOf": [DIRECT_GROUP_DN],
        },
    )

    user = ldap_backend.authenticate("alice", ALICE_PASSWORD, settings=_settings())

    assert user is not None
    assert user.is_in_required_group is True


def test_login_not_in_required_group_returns_user_flagged_unauthorized(
    directory: _FakeDirectory,
) -> None:
    """Correct password but no membership in the required group at all -
    the router turns this into a 403; the backend just reports the fact."""
    directory.add_entry(REQUIRED_GROUP_DN, {"objectClass": "group"})
    directory.add_entry(DIRECT_GROUP_DN, {"objectClass": "group"})
    directory.add_entry(
        ALICE_DN,
        {
            "sAMAccountName": "alice",
            "displayName": "Alice Example",
            "userPassword": ALICE_PASSWORD,
            "memberOf": [DIRECT_GROUP_DN],
        },
    )

    user = ldap_backend.authenticate("alice", ALICE_PASSWORD, settings=_settings())

    assert user is not None
    assert user.is_in_required_group is False


def test_user_with_no_groups_at_all_does_not_crash(directory: _FakeDirectory) -> None:
    directory.add_entry(
        ALICE_DN,
        {"sAMAccountName": "alice", "displayName": "Alice Example", "userPassword": ALICE_PASSWORD},
    )

    user = ldap_backend.authenticate("alice", ALICE_PASSWORD, settings=_settings())

    assert user is not None
    assert user.groups == []
    assert user.is_in_required_group is False


def test_wrong_password_returns_none(directory: _FakeDirectory) -> None:
    directory.add_entry(
        ALICE_DN,
        {"sAMAccountName": "alice", "displayName": "Alice Example", "userPassword": ALICE_PASSWORD},
    )

    user = ldap_backend.authenticate("alice", "totally-wrong", settings=_settings())

    assert user is None


def test_unknown_username_returns_none(directory: _FakeDirectory) -> None:
    user = ldap_backend.authenticate("nobody", "irrelevant", settings=_settings())

    assert user is None


def test_username_with_ldap_filter_metacharacters_is_escaped(directory: _FakeDirectory) -> None:
    """A username crafted to break out of the search filter (e.g.
    "alice)(sAMAccountName=*") must not match anything, proving the filter
    escapes it rather than concatenating it raw.
    """
    directory.add_entry(
        ALICE_DN,
        {"sAMAccountName": "alice", "displayName": "Alice Example", "userPassword": ALICE_PASSWORD},
    )

    user = ldap_backend.authenticate("alice)(sAMAccountName=*", "irrelevant", settings=_settings())

    assert user is None


def test_service_account_bind_failure_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the configured service account itself can't bind (e.g. wrong
    APP_LDAP_BIND_PASSWORD), authentication must fail closed, not crash.
    """
    fake = _FakeDirectory(seed_service_account=False)  # no matching userPassword stored
    fake.patch(monkeypatch)

    user = ldap_backend.authenticate("alice", "irrelevant", settings=_settings())

    assert user is None


def test_nested_group_cycle_does_not_hang_and_reports_unauthorized(
    directory: _FakeDirectory,
) -> None:
    """A misconfigured cyclic group graph (X is a member of Y and Y is a
    member of X) must terminate rather than loop forever, and correctly
    report "not authorized" when the target is never actually reached.
    """
    group_x = "CN=X,OU=Groups,DC=example,DC=local"
    group_y = "CN=Y,OU=Groups,DC=example,DC=local"
    directory.add_entry(REQUIRED_GROUP_DN, {"objectClass": "group"})
    directory.add_entry(group_x, {"objectClass": "group", "memberOf": [group_y]})
    directory.add_entry(group_y, {"objectClass": "group", "memberOf": [group_x]})
    directory.add_entry(
        ALICE_DN,
        {
            "sAMAccountName": "alice",
            "displayName": "Alice Example",
            "userPassword": ALICE_PASSWORD,
            "memberOf": [group_x],
        },
    )

    user = ldap_backend.authenticate("alice", ALICE_PASSWORD, settings=_settings())

    assert user is not None
    assert user.is_in_required_group is False


def test_group_membership_depth_limit_stops_traversal(directory: _FakeDirectory) -> None:
    """Edge case: the required group is real and reachable, but only via a
    chain longer than ldap_group_membership_max_depth - the depth cap must
    win, treating it as not-a-member rather than searching indefinitely.
    """
    group_1 = "CN=Level1,OU=Groups,DC=example,DC=local"
    group_2 = "CN=Level2,OU=Groups,DC=example,DC=local"
    directory.add_entry(REQUIRED_GROUP_DN, {"objectClass": "group"})  # 3 hops from Alice
    directory.add_entry(group_2, {"objectClass": "group", "memberOf": [REQUIRED_GROUP_DN]})
    directory.add_entry(group_1, {"objectClass": "group", "memberOf": [group_2]})
    directory.add_entry(
        ALICE_DN,
        {
            "sAMAccountName": "alice",
            "displayName": "Alice Example",
            "userPassword": ALICE_PASSWORD,
            "memberOf": [group_1],
        },
    )

    user = ldap_backend.authenticate(
        "alice", ALICE_PASSWORD, settings=_settings(ldap_group_membership_max_depth=2)
    )

    assert user is not None
    assert user.is_in_required_group is False
