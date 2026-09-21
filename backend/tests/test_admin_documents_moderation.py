"""Admin document moderation endpoints: list/detail/moderate (soft-delete +
restore) on `CandidateDocument.deleted_at`, gated by `documents:read` /
`documents:moderate` (migration 041).

INDIRECT: `app/modules/admin/documents_router.py` is not yet wired into the
Admin Module's aggregator (`app/modules/admin/__init__.py`) — that aggregation
is deliberately held back and wired centrally later (see this chunk's task
description). Per conftest.py's own documented convention ("Test files that
need different behavior... define their own local `client` fixture, which
shadows this one for that module only."), this file defines a local `client`
fixture that mounts the router directly, the same way `app/main.py` mounts
every other protected admin sub-router.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.logging import scrub_sensitive_data
from app.modules.admin.models import AdminAuditLog
from app.modules.documents.models import CandidateDocument
from tests.envelope_helpers import assert_error, assert_success

pytestmark = pytest.mark.asyncio


def _idempotency_headers(auth_headers, user_id, key: str):
    return {**auth_headers(user_id), "Idempotency-Key": key}


@pytest.fixture
def client():
    """Local override of conftest's `client` fixture: mounts the not-yet-wired
    `documents_router` onto the shared app for this module only, mirroring
    how `app/main.py` mounts every other protected admin sub-router."""
    from fastapi import Depends
    from fastapi.testclient import TestClient as _TestClient

    from app.main import app, current_verified_user
    from app.modules.admin.documents_router import router as documents_admin_router

    already_mounted = any(
        getattr(route, "path", "").startswith("/api/admin/documents") for route in app.routes
    )
    if not already_mounted:
        app.include_router(documents_admin_router, dependencies=[Depends(current_verified_user)])
    return _TestClient(app)


async def _make_document(db_session, /, **overrides) -> CandidateDocument:
    from app.auth.models import User

    owner = User(
        email=f"doc-owner-{uuid4().hex[:10]}@example.com",
        first_name="Doc",
        last_name="Owner",
        is_active=True,
        is_verified=True,
    )
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    defaults = {
        "user_id": owner.id,
        "document_type": "cv",
        "original_filename": "resume.pdf",
        "storage_path": f"documents/{uuid4().hex}/resume.pdf",
        "mime_type": "application/pdf",
        "file_hash": uuid4().hex,
        "file_size_bytes": 1024,
        "processing_status": "completed",
    }
    defaults.update(overrides)
    document = CandidateDocument(**defaults)
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def test_list_documents_requires_permission(client):
    response = client.get("/api/admin/documents")
    assert response.status_code == 401


async def test_list_documents_returns_cursor_shape(client, superuser, auth_headers, db_session):
    await _make_document(db_session)
    response = client.get("/api/admin/documents", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert "items" in body and "next_cursor" in body and "has_more" in body
    assert len(body["items"]) >= 1


async def test_list_documents_filters_by_processing_status(
    client, superuser, auth_headers, db_session
):
    unique_status = f"probe-status-{uuid4().hex[:8]}"
    matching = await _make_document(db_session, processing_status=unique_status)
    await _make_document(db_session, processing_status="completed")

    response = client.get(
        "/api/admin/documents",
        params={"processing_status": unique_status},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    ids = {item["id"] for item in body["items"]}
    assert ids == {str(matching.id)}


async def test_list_documents_filters_by_deleted(client, superuser, auth_headers, db_session):
    from datetime import UTC, datetime

    active_doc = await _make_document(db_session)
    deleted_doc = await _make_document(db_session, deleted_at=datetime.now(UTC))

    response = client.get(
        "/api/admin/documents",
        params={"deleted": True},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    ids = {item["id"] for item in body["items"]}
    assert str(deleted_doc.id) in ids
    assert str(active_doc.id) not in ids

    response = client.get(
        "/api/admin/documents",
        params={"deleted": False},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    ids = {item["id"] for item in body["items"]}
    assert str(active_doc.id) in ids
    assert str(deleted_doc.id) not in ids


async def test_get_document_detail(client, superuser, auth_headers, db_session):
    document = await _make_document(db_session)
    response = client.get(f"/api/admin/documents/{document.id}", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert body["id"] == str(document.id)
    assert body["original_filename"] == "resume.pdf"
    assert body["deleted_at"] is None


async def test_get_document_detail_not_found(client, superuser, auth_headers):
    response = client.get(f"/api/admin/documents/{uuid4()}", headers=auth_headers(superuser.id))
    assert_error(response, 404)


async def test_moderate_soft_delete_then_restore_writes_audit(
    client, superuser, auth_headers, db_session
):
    document = await _make_document(db_session)

    response = client.post(
        f"/api/admin/documents/{document.id}/moderate",
        json={"action": "soft_delete", "reason": "policy violation"},
        headers=_idempotency_headers(
            auth_headers, superuser.id, f"document-soft-delete-{document.id}"
        ),
    )
    body = assert_success(response)
    assert body["deleted_at"] is not None

    result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "documents.moderate",
            AdminAuditLog.target_id == str(document.id),
        )
    )
    entries = result.scalars().all()
    assert len(entries) == 1
    soft_delete_entry = entries[0]
    deleted_at_key = next(iter(scrub_sensitive_data({"deleted_at": None})))
    reason_key = next(iter(scrub_sensitive_data({"reason": None})))
    assert soft_delete_entry.before[deleted_at_key] is None
    assert soft_delete_entry.after[deleted_at_key] is not None
    assert soft_delete_entry.after[reason_key] == "policy violation"

    response = client.post(
        f"/api/admin/documents/{document.id}/moderate",
        json={"action": "restore", "reason": None},
        headers=_idempotency_headers(auth_headers, superuser.id, f"document-restore-{document.id}"),
    )
    body = assert_success(response)
    assert body["deleted_at"] is None

    result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "documents.moderate",
            AdminAuditLog.target_id == str(document.id),
        )
    )
    entries = result.scalars().all()
    assert len(entries) == 2
    restore_entry = next(e for e in entries if e.after[deleted_at_key] is None)
    assert restore_entry.before[deleted_at_key] is not None
    assert restore_entry.after[deleted_at_key] is None


async def test_moderate_requires_documents_moderate_permission(
    client, regular_user, auth_headers, db_session
):
    document = await _make_document(db_session)
    response = client.post(
        f"/api/admin/documents/{document.id}/moderate",
        json={"action": "soft_delete", "reason": None},
        headers=_idempotency_headers(auth_headers, regular_user.id, "document-forbidden"),
    )
    assert_error(response, 403)


async def test_support_role_can_list_and_view_but_not_moderate(
    client, support_user, auth_headers, db_session
):
    """migration 041 grants 'support' documents:read but NOT documents:moderate —
    read/detail succeed via RBAC, moderate is forbidden."""
    document = await _make_document(db_session)

    list_response = client.get("/api/admin/documents", headers=auth_headers(support_user.id))
    assert_success(list_response)

    detail_response = client.get(
        f"/api/admin/documents/{document.id}", headers=auth_headers(support_user.id)
    )
    assert_success(detail_response)

    moderate_response = client.post(
        f"/api/admin/documents/{document.id}/moderate",
        json={"action": "soft_delete", "reason": None},
        headers=_idempotency_headers(auth_headers, support_user.id, "document-support-forbidden"),
    )
    assert_error(moderate_response, 403)


async def test_moderate_requires_idempotency_key(client, superuser, auth_headers, db_session):
    document = await _make_document(db_session)
    response = client.post(
        f"/api/admin/documents/{document.id}/moderate",
        json={"action": "soft_delete", "reason": "policy violation"},
        headers=auth_headers(superuser.id),
    )
    assert_error(response, 400)


async def test_moderate_not_found_with_idempotency_key(client, superuser, auth_headers):
    response = client.post(
        f"/api/admin/documents/{uuid4()}/moderate",
        json={"action": "soft_delete", "reason": None},
        headers=_idempotency_headers(auth_headers, superuser.id, "document-404"),
    )
    assert_error(response, 404)
