"""Admin outreach moderation endpoints: list/detail/moderate + RBAC gate +
audit before/after (Admin Module, Phase 2 moderation batch).

`app/modules/admin/outreach_router.py` is not wired into the shared
`app/modules/admin/__init__.py` aggregator yet (that wiring is centralized
later, once all sibling moderation routers land — see that module's
docstring), so it is not reachable through the global `app.main.app` used by
the rest of this test suite's `client` fixture. This file defines its own
local `client` fixture that mounts only this router onto a dedicated test
app, per the pattern conftest.py documents ("Test files that need different
behavior... define their own local `client` fixture, which shadows this one
for that module only.").
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.dependencies import get_current_user_from_cookie, require_verified_user
from app.core.api_route import EnvelopeAPIRoute
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import scrub_sensitive_data
from app.modules.admin.models import AdminAuditLog
from app.modules.admin.outreach_router import router as outreach_admin_router
from app.modules.outreach.models import OutreachMessage
from tests.conftest import (
    test_auth_dependency as _test_auth_dependency,
)
from tests.envelope_helpers import assert_error, assert_success

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` — this file mixes
# sync helper functions with async test functions; pyproject.toml's
# asyncio_mode = "auto" already runs async def tests without the marker.


def _idempotency_headers(auth_headers, user_id, key: str):
    return {**auth_headers(user_id), "Idempotency-Key": key}


@pytest.fixture
def client():
    """Local TestClient mounting only outreach_admin_router — see module
    docstring for why the shared `client` fixture (bound to the real
    `app.main.app`) can't reach this not-yet-centrally-wired router."""
    test_app = FastAPI(route_class=EnvelopeAPIRoute)
    register_exception_handlers(test_app)
    test_app.include_router(outreach_admin_router)
    test_app.dependency_overrides[get_current_user_from_cookie] = _test_auth_dependency
    test_app.dependency_overrides[require_verified_user] = _test_auth_dependency
    return TestClient(test_app)


async def _make_message(db_session, *, user_id, **overrides):
    defaults = {
        "id": uuid4(),
        "user_id": user_id,
        "company_name": f"Acme {uuid4().hex[:8]}",
        "subject": "Quick intro",
        "body": "Hello there, I'd love to chat about the role.",
        "status": "draft",
    }
    defaults.update(overrides)
    message = OutreachMessage(**defaults)
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)
    return message


async def test_list_outreach_messages_requires_auth(client):
    response = client.get("/api/admin/outreach")
    assert response.status_code == 401


async def test_list_outreach_messages_regular_user_forbidden(client, regular_user, auth_headers):
    response = client.get("/api/admin/outreach", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


async def test_list_outreach_messages_filters_by_status_and_admin_blocked(
    client, superuser, regular_user, db_session, auth_headers
):
    draft_clean = await _make_message(db_session, user_id=regular_user.id, status="draft")
    draft_blocked = await _make_message(
        db_session, user_id=regular_user.id, status="draft", admin_blocked=True
    )
    sent_clean = await _make_message(db_session, user_id=regular_user.id, status="sent")

    response = client.get(
        "/api/admin/outreach",
        params={"status": "draft"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    returned_ids = {item["id"] for item in body["items"]}
    assert str(draft_clean.id) in returned_ids
    assert str(draft_blocked.id) in returned_ids
    assert str(sent_clean.id) not in returned_ids

    response = client.get(
        "/api/admin/outreach",
        params={"admin_blocked": "true"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    returned_ids = {item["id"] for item in body["items"]}
    assert str(draft_blocked.id) in returned_ids
    assert str(draft_clean.id) not in returned_ids
    assert str(sent_clean.id) not in returned_ids

    assert "next_cursor" in body and "has_more" in body


async def test_get_outreach_message_detail(
    client, superuser, regular_user, db_session, auth_headers
):
    message = await _make_message(db_session, user_id=regular_user.id)

    response = client.get(f"/api/admin/outreach/{message.id}", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert body["id"] == str(message.id)
    assert body["company_name"] == message.company_name
    assert body["admin_blocked"] is False


async def test_get_outreach_message_detail_not_found(client, superuser, auth_headers):
    response = client.get(f"/api/admin/outreach/{uuid4()}", headers=auth_headers(superuser.id))
    assert_error(response, 404)


async def test_moderate_toggles_admin_blocked_both_ways_with_audit(
    client, superuser, regular_user, db_session, auth_headers
):
    message = await _make_message(db_session, user_id=regular_user.id)

    block_response = client.post(
        f"/api/admin/outreach/{message.id}/moderate",
        json={"admin_blocked": True, "reason": "suspicious content"},
        headers=_idempotency_headers(auth_headers, superuser.id, f"outreach-block-{message.id}"),
    )
    body = assert_success(block_response)
    assert body["admin_blocked"] is True

    result = await db_session.execute(
        select(AdminAuditLog)
        .where(
            AdminAuditLog.action == "outreach.moderate",
            AdminAuditLog.target_id == str(message.id),
        )
        .order_by(AdminAuditLog.created_at.asc())
    )
    entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].before == scrub_sensitive_data({"admin_blocked": False})
    assert entries[0].after == scrub_sensitive_data(
        {"admin_blocked": True, "reason": "suspicious content"}
    )

    unblock_response = client.post(
        f"/api/admin/outreach/{message.id}/moderate",
        json={"admin_blocked": False, "reason": None},
        headers=_idempotency_headers(auth_headers, superuser.id, f"outreach-unblock-{message.id}"),
    )
    body = assert_success(unblock_response)
    assert body["admin_blocked"] is False

    result = await db_session.execute(
        select(AdminAuditLog)
        .where(
            AdminAuditLog.action == "outreach.moderate",
            AdminAuditLog.target_id == str(message.id),
        )
        .order_by(AdminAuditLog.created_at.asc())
    )
    entries = result.scalars().all()
    assert len(entries) == 2
    assert entries[1].before == scrub_sensitive_data({"admin_blocked": True})
    assert entries[1].after == scrub_sensitive_data({"admin_blocked": False, "reason": None})


async def test_moderate_not_found(client, superuser, auth_headers):
    response = client.post(
        f"/api/admin/outreach/{uuid4()}/moderate",
        json={"admin_blocked": True, "reason": None},
        headers=_idempotency_headers(auth_headers, superuser.id, "outreach-missing"),
    )
    assert_error(response, 404)


async def test_moderate_requires_outreach_moderate_permission(
    client, regular_user, db_session, auth_headers
):
    """A plain user (no role, not superuser) has neither outreach:read nor
    outreach:moderate."""
    message = await _make_message(db_session, user_id=regular_user.id)

    response = client.post(
        f"/api/admin/outreach/{message.id}/moderate",
        json={"admin_blocked": True, "reason": None},
        headers=_idempotency_headers(auth_headers, regular_user.id, "outreach-forbidden"),
    )
    assert_error(response, 403)


async def test_support_role_can_read_but_not_moderate_outreach(
    client, support_user, regular_user, db_session, auth_headers
):
    """migration 041 grants ('outreach', 'read') to 'support' but withholds
    ('outreach', 'moderate') — read-only, same shape as the users:read/
    users:suspend split in test_admin_rbac.py."""
    message = await _make_message(db_session, user_id=regular_user.id)

    read_response = client.get("/api/admin/outreach", headers=auth_headers(support_user.id))
    assert_success(read_response)

    moderate_response = client.post(
        f"/api/admin/outreach/{message.id}/moderate",
        json={"admin_blocked": True, "reason": "test"},
        headers=_idempotency_headers(auth_headers, support_user.id, "outreach-support-forbidden"),
    )
    assert_error(moderate_response, 403)


async def test_moderate_requires_idempotency_key(
    client, superuser, regular_user, db_session, auth_headers
):
    message = await _make_message(db_session, user_id=regular_user.id)
    response = client.post(
        f"/api/admin/outreach/{message.id}/moderate",
        json={"admin_blocked": True, "reason": "suspicious content"},
        headers=auth_headers(superuser.id),
    )
    assert_error(response, 400)
