"""Schema tests for the Admin Module migrations (phase2_admin_module.md §9.1)."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

pytestmark = pytest.mark.asyncio


async def test_admin_tables_exist_after_migration(db_engine):
    # NOTE: `await conn.run_sync(inspect)` alone returns an Inspector bound to
    # a sync-facade connection; calling `.get_table_names()` on it *outside*
    # that same run_sync() callback tries to do blocking I/O off the
    # greenlet SQLAlchemy's async bridge sets up, raising MissingGreenlet.
    # The fetch itself must happen inside the run_sync callback.
    async with db_engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        for table in [
            "roles",
            "permissions",
            "role_permissions",
            "admin_audit_logs",
            "feature_flags",
            "impersonation_sessions",
        ]:
            assert table in tables


async def test_users_table_has_new_columns(db_engine):
    async with db_engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("users")}
        )
        assert {"role_id", "mfa_secret", "mfa_enabled", "mfa_enrolled_at"} <= columns


async def test_seed_migration_creates_support_and_admin_roles(db_session):
    from sqlalchemy import select

    from app.modules.admin.models import Role

    result = await db_session.execute(select(Role.name))
    names = {row[0] for row in result.all()}
    assert {"support", "admin"} <= names


async def test_seed_migration_grants_expected_permissions_to_support_role(db_session):
    """Regression guard for migration 038's ROLE_PERMISSIONS mapping ('support'
    gets read + suspend only, never a write/config permission) extended by
    migration 041, which additionally grants 'support' every read-only action
    across the new Phase 2 + Module 3 resources (READ_ONLY_ACTIONS in
    041_admin_seed_phase2_permissions.py), and further extended by migration
    046, which grants 'support' read-only access to the new Module 4 resources
    (applications, interview_schedules, manual_job_entries) — never the paired
    moderate/decide action on any of these resources."""
    from sqlalchemy import select

    from app.modules.admin.models import Permission, Role, RolePermission

    result = await db_session.execute(
        select(Permission.resource, Permission.action)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .where(Role.name == "support")
    )
    granted = set(result.all())
    assert granted == {
        ("users", "read"),
        ("users", "suspend"),
        ("audit_logs", "read"),
        ("system_health", "read"),
        ("job_postings", "read"),
        ("documents", "read"),
        ("job_swipe", "read"),
        ("portfolio", "read"),
        ("outreach", "read"),
        ("content_review", "read"),
        ("questions", "read"),
        ("practice_audio", "read"),
        ("applications", "read"),
        ("interview_schedules", "read"),
        ("manual_job_entries", "read"),
    }


async def test_role_permissions_unique_constraint_on_permissions_table(db_session):
    """Migration 033's uq_permissions_resource_action must reject a duplicate
    (resource, action) pair — verifies the constraint actually exists on the
    live schema, not just in the migration source."""
    from sqlalchemy.exc import IntegrityError

    from app.modules.admin.models import Permission

    db_session.add(Permission(resource="users", action="read", description="dup"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
