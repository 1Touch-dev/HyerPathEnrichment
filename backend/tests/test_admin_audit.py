"""Audit log writer + fallback middleware tests (phase2_admin_module.md §9.2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.modules.admin.models import AdminAuditLog

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` — this file mixes
# sync and async test functions; asyncio_mode = "auto" (pyproject.toml)
# already runs async def tests without the marker, and applying it to the
# whole module also (harmlessly, but noisily) tags the sync tests.


async def test_record_admin_action_persists_entry(db_session, seed_user):
    from app.modules.admin.audit import record_admin_action

    entry = await record_admin_action(
        db_session,
        actor_user_id=seed_user.id,
        action="user.status_changed",
        target_type="user",
        target_id=str(seed_user.id),
        before={"is_active": True},
        after={"is_active": False},
        ip_address="127.0.0.1",
    )
    await db_session.commit()
    assert entry.captured_by == "explicit"
    assert entry.action == "user.status_changed"

    result = await db_session.execute(select(AdminAuditLog).where(AdminAuditLog.id == entry.id))
    persisted = result.scalar_one()
    assert persisted.before == {"is_active": True}
    assert persisted.after == {"is_active": False}


# INDIRECT (judgment call): §9.2's own sketch is explicitly illustrative — its
# comment says "the real test iterates every mutating admin route... with
# record_admin_action mocked out entirely and asserts a captured_by='fallback'
# row is written instead of silence." The literal example endpoint
# ("/api/admin/some-endpoint-without-explicit-audit") does not exist. Below,
# two real mutating admin routes (from two different routers, per the plan's
# "iterates every mutating admin route" intent) are exercised with the
# explicit `record_admin_action` call patched out, proving
# AdminAuditFallbackMiddleware (app/modules/admin/audit.py) is the safety net
# that still writes an audit row when a router forgets to call it.
@pytest.mark.parametrize(
    ("method", "path", "json_body", "patch_target"),
    [
        (
            "PUT",
            "/api/admin/feature-flags/fallback_test_flag",
            {"enabled": True, "value": None, "description": "fallback probe"},
            "app.modules.admin.service.record_admin_action",
        ),
    ],
)
def test_fallback_middleware_logs_uncaptured_mutation(
    client, superuser, auth_headers, method, path, json_body, patch_target
):
    with patch(patch_target, new=AsyncMock(return_value=None)):
        response = client.request(method, path, json=json_body, headers=auth_headers(superuser.id))
    assert response.status_code < 500

    import asyncio

    from app.database.session import SessionLocal

    async def _fetch():
        async with SessionLocal() as session:
            result = await session.execute(
                select(AdminAuditLog).where(
                    AdminAuditLog.captured_by == "fallback",
                    AdminAuditLog.action == f"{method.lower()}_{path}",
                )
            )
            return result.scalars().all()

    rows = asyncio.run(_fetch())
    assert len(rows) == 1
    assert rows[0].after == {"status_code": response.status_code}


async def test_explicit_audit_call_suppresses_fallback_logging(client, superuser, auth_headers):
    """Sanity counterpart to the fallback test above: when the router DOES call
    record_admin_action (the normal, non-mocked path), the fallback middleware
    must not also write a second, redundant 'unclassified' row for the same
    request."""
    response = client.put(
        "/api/admin/feature-flags/normal_flow_flag",
        json={"enabled": True, "value": None, "description": "normal probe"},
        headers=auth_headers(superuser.id),
    )
    assert response.status_code == 200

    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        result = await session.execute(
            select(AdminAuditLog).where(
                AdminAuditLog.target_id == "normal_flow_flag",
                AdminAuditLog.captured_by == "fallback",
            )
        )
        assert result.scalars().all() == []
