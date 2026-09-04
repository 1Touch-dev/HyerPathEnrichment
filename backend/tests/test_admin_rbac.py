"""require_permission() behavior: superuser bypass, role-based grant/deny
(phase2_admin_module.md §9.5)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` here — this file
# mixes sync and async test functions, and pyproject.toml's asyncio_mode =
# "auto" already handles async def tests automatically; applying the marker
# to the whole module also (harmlessly, but noisily) tags the sync tests,
# which pytest-asyncio warns about.


async def test_superuser_bypasses_rbac_lookup(db_session, superuser):
    from app.modules.admin.permissions import user_has_permission

    assert await user_has_permission(db_session, superuser, "nonexistent", "resource") is True


async def test_user_without_role_denied(db_session, regular_user):
    from app.modules.admin.permissions import user_has_permission

    assert await user_has_permission(db_session, regular_user, "users", "read") is False


async def test_support_role_can_read_users_but_not_write(db_session, support_user):
    from app.modules.admin.permissions import user_has_permission

    assert await user_has_permission(db_session, support_user, "users", "read") is True
    assert await user_has_permission(db_session, support_user, "users", "write") is False


async def test_support_role_can_suspend_users(db_session, support_user):
    """migration 038 grants ('users', 'suspend') to 'support' — distinct from
    ('users', 'write'), which it does NOT grant."""
    from app.modules.admin.permissions import user_has_permission

    assert await user_has_permission(db_session, support_user, "users", "suspend") is True


async def test_sqlite_permission_lookup_matches_dashed_and_undashed_uuids(db_session):
    if db_session.bind.dialect.name != "sqlite":
        pytest.skip("SQLite storage parity regression test")

    from app.auth.models import User
    from app.modules.admin.models import Permission, Role
    from app.modules.admin.permissions import user_has_permission

    role = Role(name=f"uuid-parity-{uuid4().hex}", is_system=False)
    permission = Permission(resource=f"uuid-parity-{uuid4().hex}", action="read")
    db_session.add_all([role, permission])
    await db_session.commit()
    await db_session.refresh(role)
    await db_session.refresh(permission)

    await db_session.execute(
        text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "VALUES (:role_id, :permission_id)"
        ),
        {"role_id": str(role.id), "permission_id": str(permission.id)},
    )
    user = User(
        email=f"uuid-parity-{uuid4().hex}@example.com",
        first_name="UUID",
        last_name="Parity",
        is_active=True,
        is_verified=True,
        role_id=role.id,
    )
    db_session.add(user)
    await db_session.commit()

    stored_ids = (
        await db_session.execute(
            text(
                "SELECT role_id, permission_id FROM role_permissions "
                "WHERE role_id = :role_id AND permission_id = :permission_id"
            ),
            {"role_id": str(role.id), "permission_id": str(permission.id)},
        )
    ).one()
    assert stored_ids == (str(role.id), str(permission.id))
    assert (
        await user_has_permission(db_session, user, permission.resource, permission.action) is True
    )


def test_require_superuser_strict_rejects_non_superuser(regular_user):
    from fastapi import HTTPException

    from app.modules.admin.permissions import require_superuser_strict

    with pytest.raises(HTTPException) as exc:
        require_superuser_strict(regular_user)
    assert exc.value.status_code == 403


def test_require_superuser_strict_allows_superuser(superuser):
    from app.modules.admin.permissions import require_superuser_strict

    assert require_superuser_strict(superuser) is superuser


async def test_existing_require_superuser_call_sites_unaffected(client):
    """Regression guard for Decision 1 — the 5 pre-existing cost endpoints must
    keep working exactly as before this module's changes."""
    response = client.get("/api/admin/costs/daily")
    assert response.status_code == 401  # unauthenticated, same as before this plan
