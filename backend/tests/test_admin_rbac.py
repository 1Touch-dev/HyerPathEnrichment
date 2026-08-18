"""require_permission() behavior: superuser bypass, role-based grant/deny
(phase2_admin_module.md §9.5)."""

from __future__ import annotations

import pytest

from tests.conftest import SQLITE_ROLE_UUID_DASH_BUG_REASON

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


@pytest.mark.xfail(reason=SQLITE_ROLE_UUID_DASH_BUG_REASON, strict=True)
async def test_support_role_can_read_users_but_not_write(db_session, support_user):
    from app.modules.admin.permissions import user_has_permission

    assert await user_has_permission(db_session, support_user, "users", "read") is True
    assert await user_has_permission(db_session, support_user, "users", "write") is False


@pytest.mark.xfail(reason=SQLITE_ROLE_UUID_DASH_BUG_REASON, strict=True)
async def test_support_role_can_suspend_users(db_session, support_user):
    """migration 038 grants ('users', 'suspend') to 'support' — distinct from
    ('users', 'write'), which it does NOT grant."""
    from app.modules.admin.permissions import user_has_permission

    assert await user_has_permission(db_session, support_user, "users", "suspend") is True


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
