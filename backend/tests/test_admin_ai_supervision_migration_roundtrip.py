"""Round-trip test for 053_ai_action_audit_log (machine-2-parallel-tracks/
04-rbac-admin-platform.md's AI-agent supervision Verification section):
upgrade -> downgrade -> upgrade again, confirming the seed migration's
downgrade removes only the `ai_supervision:read` permission (and its
`role_permissions` grant) it added -- never a pre-existing `Permission` row
it merely looked up (the "admin" role itself) -- and the `ai_action_audit_log`
table is fully created/dropped cleanly.

Follows the exact pattern in `test_admin_roles_migration_roundtrip.py`:
targets the specific revisions under test (`REV_BEFORE`/`REV_THIS`) rather
than a relative `downgrade -1`, since the live migration graph has multiple
parallel-track branches merged upstream of this revision.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text as sa_text

from alembic import command
from tests.migration_helpers import alembic_config, sqlite_file_url, sync_engine_for, table_names

REV_BEFORE = "051_merge_machine2_parallel_track_heads"
REV_THIS = "053_ai_action_audit_log"

NEW_PERMISSION = ("ai_supervision", "read")


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return sqlite_file_url(tmp_path / "ai_action_audit_log_migrate.db")


def _upgrade_to(url: str, revision: str) -> None:
    command.upgrade(alembic_config(url), revision)


def _downgrade_to(url: str, revision: str) -> None:
    command.downgrade(alembic_config(url), revision)


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


class TestUpgradeCreatesTableAndSeedsPermission:
    def test_table_created(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        assert "ai_action_audit_log" in table_names(sqlite_url)

    def test_permission_seeded(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        assert NEW_PERMISSION in _permission_pairs(sqlite_url)

    def test_admin_role_granted_permission(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        granted = _role_permission_pairs_for_role(sqlite_url, "admin")
        assert NEW_PERMISSION in granted


class TestDowngradeRemovesOnlyOwnedRows:
    def test_downgrade_drops_table(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)
        assert "ai_action_audit_log" not in table_names(sqlite_url)

    def test_downgrade_removes_seeded_permission(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)
        assert NEW_PERMISSION not in _permission_pairs(sqlite_url)

    def test_downgrade_removes_role_permission_grant(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)
        granted = _role_permission_pairs_for_role(sqlite_url, "admin")
        assert NEW_PERMISSION not in granted

    def test_downgrade_preserves_admin_role_and_its_other_permissions(self, sqlite_url: str):
        """The admin role itself, and every permission it already had before
        this migration ran, must survive the downgrade untouched -- this
        migration only ever deletes the one (resource, action) pair (and its
        grant row) that it itself inserted."""
        _upgrade_to(sqlite_url, REV_BEFORE)
        before_grants = _role_permission_pairs_for_role(sqlite_url, "admin")

        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)
        after_grants = _role_permission_pairs_for_role(sqlite_url, "admin")

        assert after_grants == before_grants


class TestFullRoundTrip:
    def test_upgrade_downgrade_upgrade_is_clean(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)
        _upgrade_to(sqlite_url, REV_THIS)

        assert "ai_action_audit_log" in table_names(sqlite_url)
        assert NEW_PERMISSION in _permission_pairs(sqlite_url)
        assert NEW_PERMISSION in _role_permission_pairs_for_role(sqlite_url, "admin")

    def test_upgrade_downgrade_upgrade_does_not_duplicate_permission_rows(self, sqlite_url: str):
        """Re-upgrading must not create a second `Permission` row for
        `ai_supervision:read` -- the migration always inserts a fresh row
        without checking for an existing one first (unlike 047's
        reused-permission lookups), so this specifically guards against ever
        running this migration's upgrade twice against the same DB without an
        intervening downgrade, and confirms one full upgrade->downgrade->
        upgrade cycle leaves exactly one row, not two."""
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
