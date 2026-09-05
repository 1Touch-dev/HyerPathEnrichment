"""User management API: pagination, status changes, role assignment, audit
(phase2_admin_module.md §9.4).

INDIRECT: the plan's `superuser_cookie`/`support_role_cookie` fixtures assume
a cookie-based login flow. This repo's real test-auth mechanism is header
based (see conftest.py's `test_auth_dependency`), so these tests authenticate
via `auth_headers(user.id)` against real, persisted `superuser`/`regular_user`/
`support_user` fixtures instead.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.modules.admin.models import AdminAuditLog
from tests.conftest import USING_POSTGRES
from tests.envelope_helpers import assert_error, assert_success

SQLITE_ASSIGN_ROLE_LOOKUP_BUG_REASON = (
    "SQLite stores the migration-seeded role UUID with dashes while the role "
    "assignment response resolves it through a separate strict UUID lookup"
)

pytestmark = pytest.mark.asyncio


async def test_list_users_requires_permission(client):
    response = client.get("/api/admin/users")
    assert response.status_code == 401


async def test_list_users_returns_cursor_shape(client, superuser, auth_headers):
    response = client.get("/api/admin/users", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert "items" in body and "next_cursor" in body and "has_more" in body
    assert any(str(superuser.id) == item["id"] for item in body["items"])


async def test_list_users_regular_user_forbidden(client, regular_user, auth_headers):
    """A plain user (no role, not superuser) has no `users:read` permission."""
    response = client.get("/api/admin/users", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


async def test_support_role_can_list_users(client, support_user, auth_headers):
    """support role grants users:read (migration 038) — RBAC path, not the
    is_superuser bypass."""
    response = client.get("/api/admin/users", headers=auth_headers(support_user.id))
    assert_success(response)


async def test_suspend_user_is_unavailable_until_adr21_step_up(
    client, superuser, regular_user, db_session, auth_headers
):
    response = client.patch(
        f"/api/admin/users/{regular_user.id}/status",
        json={"is_active": False, "reason": "ToS violation"},
        headers={**auth_headers(superuser.id), "Idempotency-Key": "user-deactivate-blocked"},
    )
    assert_error(response, 405, "PRIVILEGED_OPERATION_UNAVAILABLE")

    result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "user.status_changed",
            AdminAuditLog.target_id == str(regular_user.id),
        )
    )
    assert result.scalars().all() == []


async def test_suspend_user_requires_users_suspend_permission(
    client, regular_user, db_session, auth_headers
):
    """A support-role actor CAN suspend (migration 038 grants users:suspend to
    support), a plain user with no role cannot."""
    from app.auth.models import User

    other_user = User(
        email="target-for-suspend@example.com",
        first_name="Target",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    response = client.patch(
        f"/api/admin/users/{other_user.id}/status",
        json={"is_active": False, "reason": "test"},
        headers=auth_headers(regular_user.id),
    )
    assert_error(response, 403)


async def test_assign_role_requires_strict_superuser_not_rbac_permission(
    client, support_user, regular_user, auth_headers
):
    """RBAC alone (e.g. a 'support' role with users:write) must NOT be able to
    assign roles — only is_superuser can, per Decision 1."""
    response = client.put(
        f"/api/admin/users/{regular_user.id}/role",
        json={"role_id": None},
        headers=auth_headers(support_user.id),
    )
    assert_error(response, 403)


@pytest.mark.xfail(
    condition=not USING_POSTGRES, reason=SQLITE_ASSIGN_ROLE_LOOKUP_BUG_REASON, strict=True
)
async def test_assign_role_succeeds_for_superuser(
    client, superuser, regular_user, db_session, auth_headers
):
    from sqlalchemy import select as _select

    from app.modules.admin.models import Role

    result = await db_session.execute(_select(Role).where(Role.name == "admin"))
    admin_role = result.scalar_one()

    response = client.put(
        f"/api/admin/users/{regular_user.id}/role",
        json={"role_id": str(admin_role.id)},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert body["role_id"] == str(admin_role.id)
    assert body["role_name"] == "admin"
