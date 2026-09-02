"""Focused migration tests for the Product Doors team_owner grants."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, text as sa_text

from alembic import command
from alembic.script import ScriptDirectory
from tests.migration_helpers import alembic_config, sqlite_file_url, sync_engine_for

REV_BEFORE = "060_merge_security_p1_and_billing_heads"
REV_THIS = "061_team_owner_full_desk_grants"
TRACKING_TABLE = "migration_061_team_owner_grants"

EXPECTED_DESK_PERMISSIONS = {
    ("ai_supervision", "read"),
    ("analytics", "read"),
    ("applications", "read"),
    ("audit_logs", "read"),
    ("brands", "delete"),
    ("brands", "read"),
    ("brands", "write"),
    ("content_review", "decide"),
    ("content_review", "read"),
    ("documents", "moderate"),
    ("documents", "read"),
    ("documents", "write"),
    ("feature_flags", "read"),
    ("feature_flags", "write"),
    ("impersonation", "start"),
    ("interview_schedules", "moderate"),
    ("interview_schedules", "read"),
    ("job_postings", "moderate"),
    ("job_postings", "read"),
    ("job_postings", "write"),
    ("job_swipe", "read"),
    ("linkedin_sourcing", "write"),
    ("linkedin_tasks", "operate"),
    ("manual_job_entries", "moderate"),
    ("manual_job_entries", "read"),
    ("outreach", "moderate"),
    ("outreach", "read"),
    ("outreach", "write"),
    ("portfolio", "moderate"),
    ("portfolio", "read"),
    ("portfolio", "write"),
    ("practice_audio", "moderate"),
    ("practice_audio", "read"),
    ("questions", "moderate"),
    ("questions", "read"),
    ("queues", "read"),
    ("queues", "retry"),
    ("recruiter_actions", "write"),
    ("recruiter_assignments", "write"),
    ("roles", "read"),
    ("roles", "write"),
    ("system_health", "read"),
    ("users", "read"),
    ("users", "suspend"),
    ("users", "write"),
}


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return sqlite_file_url(tmp_path / "team_owner_desk_grants.db")


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


def _team_owner_grants(url: str) -> set[tuple[str, str]]:
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
                    WHERE r.name = 'team_owner'
                    """
                )
            ).fetchall()
            return {(row[0], row[1]) for row in rows}
    finally:
        engine.dispose()


def _table_names(url: str) -> set[str]:
    engine = sync_engine_for(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_revision_is_the_only_migration_head() -> None:
    script = ScriptDirectory.from_config(alembic_config("sqlite://"))
    assert script.get_heads() == [REV_THIS]


def test_upgrade_downgrade_upgrade_preserves_existing_rows(sqlite_url: str) -> None:
    _upgrade_to(sqlite_url, REV_BEFORE)
    permissions_before = _permission_pairs(sqlite_url)
    grants_before = _team_owner_grants(sqlite_url)

    engine = sync_engine_for(sqlite_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa_text(
                    """
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT r.id, p.id
                    FROM roles r
                    CROSS JOIN permissions p
                    WHERE r.name = 'team_owner'
                      AND p.resource = 'analytics'
                      AND p.action = 'read'
                    """
                )
            )
    finally:
        engine.dispose()
    preexisting_extra_grant = ("analytics", "read")

    _upgrade_to(sqlite_url, REV_THIS)
    assert _team_owner_grants(sqlite_url) == EXPECTED_DESK_PERMISSIONS
    assert _permission_pairs(sqlite_url) == permissions_before
    assert TRACKING_TABLE in _table_names(sqlite_url)

    _downgrade_to(sqlite_url, REV_BEFORE)
    assert _team_owner_grants(sqlite_url) == grants_before | {preexisting_extra_grant}
    assert _permission_pairs(sqlite_url) == permissions_before
    assert TRACKING_TABLE not in _table_names(sqlite_url)

    _upgrade_to(sqlite_url, REV_THIS)
    assert _team_owner_grants(sqlite_url) == EXPECTED_DESK_PERMISSIONS
    assert _permission_pairs(sqlite_url) == permissions_before


@pytest.mark.parametrize(
    ("missing_kind", "delete_sql", "expected_message"),
    [
        (
            "role",
            "DELETE FROM roles WHERE name = 'team_owner'",
            "requires the team_owner role",
        ),
        (
            "permission",
            ("DELETE FROM permissions WHERE resource = 'analytics' AND action = 'read'"),
            "missing expected permission rows: analytics:read",
        ),
    ],
)
def test_upgrade_fails_clearly_when_seed_rows_are_missing(
    sqlite_url: str,
    missing_kind: str,
    delete_sql: str,
    expected_message: str,
) -> None:
    _upgrade_to(sqlite_url, REV_BEFORE)
    engine = sync_engine_for(sqlite_url)
    try:
        with engine.begin() as conn:
            if missing_kind == "role":
                conn.execute(
                    sa_text(
                        """
                        DELETE FROM role_permissions
                        WHERE role_id = (SELECT id FROM roles WHERE name = 'team_owner')
                        """
                    )
                )
            else:
                conn.execute(
                    sa_text(
                        """
                        DELETE FROM role_permissions
                        WHERE permission_id = (
                            SELECT id FROM permissions
                            WHERE resource = 'analytics' AND action = 'read'
                        )
                        """
                    )
                )
            conn.execute(sa_text(delete_sql))
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match=expected_message):
        _upgrade_to(sqlite_url, REV_THIS)
