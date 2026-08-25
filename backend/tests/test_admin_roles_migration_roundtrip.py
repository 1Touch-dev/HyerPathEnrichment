"""Round-trip test for 047_seed_system_roles (machine-2-parallel-tracks/
04-rbac-admin-platform.md's Verification section): upgrade -> downgrade ->
upgrade again, confirming the seed migration's downgrade removes only the
rows it added (the `team_owner`/`recruiter` roles, their `role_permissions`
rows, and the four brand-new "write" permissions it owns) and never a
pre-existing `Permission` row (e.g. `users:read`, `roles:write`) it merely
looked up and reused.

Follows the pattern in `test_demand_intelligence_migrations.py` /
`test_job_matching_migrations.py`: run against a real SQLite file via
Alembic's `upgrade`/`downgrade` commands (not `create_all`), then inspect the
resulting rows directly. Targets the specific revisions under test
(`REV_BEFORE`/`REV_THIS`) rather than a relative `downgrade -1`, since the
live migration graph has multiple parallel-track branches merged at
`051_merge_machine2_parallel_track_heads` — a relative `-1` from `head` is
ambiguous across a merge point, whereas targeting `047_seed_system_roles`
explicitly is not.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text as sa_text

from alembic import command
from tests.migration_helpers import alembic_config, sqlite_file_url, sync_engine_for

REV_BEFORE = "046_admin_seed_module4_permissions"
REV_THIS = "047_seed_system_roles"

# Mirrors 047_seed_system_roles.py's own NEW_PERMISSIONS_OWNED_BY_THIS_MIGRATION:
# the only (resource, action) pairs that did not exist prior to this migration.
NEW_PERMISSIONS_OWNED_BY_THIS_MIGRATION = {
    ("outreach", "write"),
    ("documents", "write"),
    ("portfolio", "write"),
    ("job_postings", "write"),
}

# Pairs the migration looks up and reuses (already seeded by 038/041) — must
# never be deleted by this migration's downgrade.
PRE_EXISTING_PERMISSIONS_MERELY_REFERENCED = {
    ("users", "read"),
    ("users", "write"),
    ("roles", "read"),
    ("roles", "write"),
}


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return sqlite_file_url(tmp_path / "admin_roles_migrate.db")


def _upgrade_to(url: str, revision: str) -> None:
    command.upgrade(alembic_config(url), revision)


def _downgrade_to(url: str, revision: str) -> None:
    command.downgrade(alembic_config(url), revision)


def _role_names(url: str) -> set[str]:
    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(sa_text("SELECT name FROM roles")).fetchall()
            return {row[0] for row in rows}
    finally:
        engine.dispose()


def _permission_pairs(url: str) -> set[tuple[str, str]]:
    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(sa_text("SELECT resource, action FROM permissions")).fetchall()
            return {(row[0], row[1]) for row in rows}
    finally:
        engine.dispose()


def _role_permission_pairs_for_role(url: str, role_name: str) -> set[tuple[str, str]]:
    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sa_text(
                    """
                    SELECT p.resource, p.action
                    FROM role_permissions rp
                    JOIN permissions p ON p.id = rp.permission_id
                    JOIN roles r ON r.id = rp.role_id
                    WHERE r.name = :role_name
                    """
                ),
                {"role_name": role_name},
            ).fetchall()
            return {(row[0], row[1]) for row in rows}
    finally:
        engine.dispose()


class TestUpgradeSeedsSystemRoles:
    def test_team_owner_and_recruiter_roles_created(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        assert {"team_owner", "recruiter"} <= _role_names(sqlite_url)

    def test_new_write_permissions_created(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        assert NEW_PERMISSIONS_OWNED_BY_THIS_MIGRATION <= _permission_pairs(sqlite_url)

    def test_team_owner_gets_full_permission_set(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        granted = _role_permission_pairs_for_role(sqlite_url, "team_owner")
        assert granted == {
            ("users", "read"),
            ("users", "write"),
            ("outreach", "read"),
            ("outreach", "write"),
            ("documents", "read"),
            ("documents", "write"),
            ("portfolio", "read"),
            ("portfolio", "write"),
            ("job_postings", "read"),
            ("job_postings", "write"),
            ("roles", "read"),
            ("roles", "write"),
        }

    def test_recruiter_gets_no_roles_access(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        granted = _role_permission_pairs_for_role(sqlite_url, "recruiter")
        assert ("roles", "read") not in granted
        assert ("roles", "write") not in granted
        assert ("users", "write") not in granted
        assert ("users", "read") in granted


class TestDowngradeRemovesOnlyOwnedRows:
    def test_downgrade_removes_seeded_roles(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)
        assert _role_names(sqlite_url).isdisjoint({"team_owner", "recruiter"})

    def test_downgrade_removes_only_permissions_this_migration_owns(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)
        remaining = _permission_pairs(sqlite_url)
        assert remaining.isdisjoint(NEW_PERMISSIONS_OWNED_BY_THIS_MIGRATION)

    def test_downgrade_preserves_pre_existing_referenced_permissions(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)
        remaining = _permission_pairs(sqlite_url)
        assert PRE_EXISTING_PERMISSIONS_MERELY_REFERENCED <= remaining

    def test_downgrade_removes_role_permission_rows_for_removed_roles(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)
        assert _role_permission_pairs_for_role(sqlite_url, "team_owner") == set()
        assert _role_permission_pairs_for_role(sqlite_url, "recruiter") == set()


class TestFullRoundTrip:
    def test_upgrade_downgrade_upgrade_is_clean(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)
        _upgrade_to(sqlite_url, REV_THIS)

        assert {"team_owner", "recruiter"} <= _role_names(sqlite_url)
        assert NEW_PERMISSIONS_OWNED_BY_THIS_MIGRATION <= _permission_pairs(sqlite_url)
        assert PRE_EXISTING_PERMISSIONS_MERELY_REFERENCED <= _permission_pairs(sqlite_url)

        granted = _role_permission_pairs_for_role(sqlite_url, "team_owner")
        assert granted == {
            ("users", "read"),
            ("users", "write"),
            ("outreach", "read"),
            ("outreach", "write"),
            ("documents", "read"),
            ("documents", "write"),
            ("portfolio", "read"),
            ("portfolio", "write"),
            ("job_postings", "read"),
            ("job_postings", "write"),
            ("roles", "read"),
            ("roles", "write"),
        }

    def test_upgrade_downgrade_upgrade_does_not_duplicate_permission_rows(self, sqlite_url: str):
        """Re-upgrading must not create a second `Permission` row for a pair
        that still exists (e.g. `users:read`, never removed by downgrade) —
        the `SELECT ... WHERE resource = :resource AND action = :action`
        lookup in `upgrade()` must reuse it instead of inserting a duplicate,
        which the `uq_permissions_resource_action` constraint would reject
        anyway if violated."""
        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)
        _upgrade_to(sqlite_url, REV_THIS)

        engine = sync_engine_for(sqlite_url)
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    sa_text(
                        "SELECT resource, action, COUNT(*) FROM permissions "
                        "GROUP BY resource, action HAVING COUNT(*) > 1"
                    )
                ).fetchall()
        finally:
            engine.dispose()
        assert rows == []
