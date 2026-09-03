"""Tests for the generic review-queue router: listing/filtering, detail
resolution, RBAC gate, and the decide flow's domain-column flips (Batch 1).

Domain rows (job_postings/candidate_documents/outreach_messages) are inserted
via raw sa.table() inserts rather than importing the domain ORM models — see
review_queue_router.py's module docstring for why.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa

from app.modules.admin.models import AdminReviewQueueItem

pytestmark = pytest.mark.asyncio

# review_queue_router is a Batch-1 chunk that is deliberately NOT wired into
# app.modules.admin.__init__'s router aggregator yet (per plan — wiring is
# centralized in a later batch). To exercise it at the real HTTP layer
# without touching that file, mount it onto the shared app for the duration
# of each test in this module and unmount it afterwards — same pattern
# test_api_envelopes.py already uses for a temporary test-only router.
_REVIEW_QUEUE_PREFIX = "/api/admin/review-queue"


@pytest.fixture(autouse=True)
def _mount_review_queue_router():
    """`review_queue_router` is now wired permanently into
    `app/modules/admin/__init__.py`'s aggregator, so the real `app` singleton
    already has these routes mounted at import time. Only mount (and later
    unmount) here if that isn't already the case, so this test never tears
    down the permanently-wired production routes out from under other test
    modules that run afterward in the same session."""
    from app.main import app
    from app.modules.admin.review_queue_router import router as review_queue_router

    already_mounted = any(
        getattr(route, "path", "").startswith(_REVIEW_QUEUE_PREFIX) for route in app.routes
    )
    if already_mounted:
        yield
        return
    app.include_router(review_queue_router)
    try:
        yield
    finally:
        app.routes[:] = [
            route
            for route in app.routes
            if not getattr(route, "path", "").startswith(_REVIEW_QUEUE_PREFIX)
        ]


async def _make_queue_item(
    db_session,
    *,
    resource_type: str,
    resource_id,
    status: str = "pending",
    flag_source: str = "heuristic",
    flag_reason: str | None = "test flag",
):
    item = AdminReviewQueueItem(
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        flag_reason=flag_reason,
        flag_source=flag_source,
        flagged_at=datetime.now(UTC),
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


async def _insert_job_posting(db_session, *, moderation_status: str = "active"):
    posting_id = uuid4()
    table = sa.table(
        "job_postings",
        sa.column("id", sa.Uuid()),
        sa.column("dedup_key"),
        sa.column("title"),
        sa.column("company"),
        sa.column("location"),
        sa.column("remote"),
        sa.column("source"),
        sa.column("first_seen_at"),
        sa.column("last_seen_at"),
        sa.column("moderation_status"),
    )
    now = datetime.now(UTC)
    await db_session.execute(
        table.insert().values(
            id=posting_id,
            dedup_key=f"dedup-{uuid4().hex}",
            title="Backend Engineer",
            company="Acme Corp",
            location="Remote",
            remote=True,
            source="linkedin",
            first_seen_at=now,
            last_seen_at=now,
            moderation_status=moderation_status,
        )
    )
    await db_session.commit()
    return posting_id


async def _insert_candidate_document(db_session, user_id):
    document_id = uuid4()
    table = sa.table(
        "candidate_documents",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("document_type"),
        sa.column("original_filename"),
        sa.column("storage_path"),
        sa.column("file_hash"),
        sa.column("file_size_bytes"),
        sa.column("processing_status"),
    )
    await db_session.execute(
        table.insert().values(
            id=document_id,
            user_id=user_id,
            document_type="cv",
            original_filename="resume.pdf",
            storage_path="/tmp/resume.pdf",
            file_hash=uuid4().hex,
            file_size_bytes=1024,
            processing_status="completed",
        )
    )
    await db_session.commit()
    return document_id


async def _insert_outreach_message(db_session, user_id):
    message_id = uuid4()
    table = sa.table(
        "outreach_messages",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("company_name"),
        sa.column("subject"),
        sa.column("body"),
        sa.column("created_at"),
    )
    await db_session.execute(
        table.insert().values(
            id=message_id,
            user_id=user_id,
            company_name="Acme Corp",
            subject="Interested in the role",
            body="Hello, I'd love to chat.",
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    return message_id


async def test_list_review_queue_returns_items(client, superuser, db_session, auth_headers):
    await _make_queue_item(db_session, resource_type="job_posting", resource_id=uuid4())
    await _make_queue_item(db_session, resource_type="document", resource_id=uuid4())

    response = client.get("/api/admin/review-queue", headers=auth_headers(superuser.id))
    assert response.status_code == 200
    body = response.json()["data"]
    assert len(body["items"]) >= 2


async def test_list_review_queue_filters_by_resource_type(
    client, superuser, db_session, auth_headers
):
    marker_type = f"document-{uuid4().hex[:8]}"
    await _make_queue_item(db_session, resource_type=marker_type, resource_id=uuid4())
    await _make_queue_item(db_session, resource_type="job_posting", resource_id=uuid4())

    response = client.get(
        "/api/admin/review-queue",
        params={"resource_type": marker_type},
        headers=auth_headers(superuser.id),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert all(item["resource_type"] == marker_type for item in body["items"])
    assert len(body["items"]) == 1


async def test_list_review_queue_filters_by_status(client, superuser, db_session, auth_headers):
    marker_type = f"probe-{uuid4().hex[:8]}"
    await _make_queue_item(
        db_session, resource_type=marker_type, resource_id=uuid4(), status="pending"
    )
    await _make_queue_item(
        db_session, resource_type=marker_type, resource_id=uuid4(), status="approved"
    )

    response = client.get(
        "/api/admin/review-queue",
        params={"resource_type": marker_type, "status": "approved"},
        headers=auth_headers(superuser.id),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == "approved"


async def test_detail_resolves_job_posting_resource(client, superuser, db_session, auth_headers):
    posting_id = await _insert_job_posting(db_session)
    item = await _make_queue_item(db_session, resource_type="job_posting", resource_id=posting_id)

    response = client.get(f"/api/admin/review-queue/{item.id}", headers=auth_headers(superuser.id))
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["resolved_resource"] is not None
    assert body["resolved_resource"]["title"] == "Backend Engineer"


async def test_detail_module3_placeholder_resolves_to_none(
    client, superuser, db_session, auth_headers
):
    item = await _make_queue_item(db_session, resource_type="question", resource_id=uuid4())

    response = client.get(f"/api/admin/review-queue/{item.id}", headers=auth_headers(superuser.id))
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["resolved_resource"] is None


async def test_detail_missing_resource_resolves_to_none(
    client, superuser, db_session, auth_headers
):
    item = await _make_queue_item(db_session, resource_type="job_posting", resource_id=uuid4())

    response = client.get(f"/api/admin/review-queue/{item.id}", headers=auth_headers(superuser.id))
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["resolved_resource"] is None


async def test_decide_requires_content_review_read_for_list(client, support_user, auth_headers):
    response = client.get("/api/admin/review-queue", headers=auth_headers(support_user.id))
    assert response.status_code == 200


async def test_decide_forbidden_for_support_role(client, support_user, db_session, auth_headers):
    item = await _make_queue_item(db_session, resource_type="job_posting", resource_id=uuid4())

    response = client.post(
        f"/api/admin/review-queue/{item.id}/decide",
        json={"status": "approved", "review_notes": None},
        headers=auth_headers(support_user.id),
    )
    assert response.status_code == 403


async def test_decide_approve_does_not_touch_domain_column(
    client, superuser, db_session, auth_headers
):
    posting_id = await _insert_job_posting(db_session)
    item = await _make_queue_item(db_session, resource_type="job_posting", resource_id=posting_id)

    response = client.post(
        f"/api/admin/review-queue/{item.id}/decide",
        json={"status": "approved", "review_notes": "looks fine"},
        headers=auth_headers(superuser.id),
    )
    assert response.status_code == 200

    table = sa.table("job_postings", sa.column("id", sa.Uuid()), sa.column("moderation_status"))
    result = await db_session.execute(
        sa.select(table.c.moderation_status).where(table.c.id == posting_id)
    )
    assert result.scalar_one() == "active"


async def test_decide_reject_job_posting_sets_moderation_status_removed(
    client, superuser, db_session, auth_headers
):
    posting_id = await _insert_job_posting(db_session)
    item = await _make_queue_item(db_session, resource_type="job_posting", resource_id=posting_id)

    response = client.post(
        f"/api/admin/review-queue/{item.id}/decide",
        json={"status": "rejected", "review_notes": "spam"},
        headers=auth_headers(superuser.id),
    )
    assert response.status_code == 200

    table = sa.table("job_postings", sa.column("id", sa.Uuid()), sa.column("moderation_status"))
    result = await db_session.execute(
        sa.select(table.c.moderation_status).where(table.c.id == posting_id)
    )
    assert result.scalar_one() == "removed"


async def test_decide_reject_document_sets_deleted_at(
    client, superuser, regular_user, db_session, auth_headers
):
    document_id = await _insert_candidate_document(db_session, regular_user.id)
    item = await _make_queue_item(db_session, resource_type="document", resource_id=document_id)

    response = client.post(
        f"/api/admin/review-queue/{item.id}/decide",
        json={"status": "rejected", "review_notes": "policy violation"},
        headers=auth_headers(superuser.id),
    )
    assert response.status_code == 200

    table = sa.table("candidate_documents", sa.column("id", sa.Uuid()), sa.column("deleted_at"))
    result = await db_session.execute(
        sa.select(table.c.deleted_at).where(table.c.id == document_id)
    )
    assert result.scalar_one() is not None


async def test_decide_reject_outreach_message_sets_admin_blocked(
    client, superuser, regular_user, db_session, auth_headers
):
    message_id = await _insert_outreach_message(db_session, regular_user.id)
    item = await _make_queue_item(
        db_session, resource_type="outreach_message", resource_id=message_id
    )

    response = client.post(
        f"/api/admin/review-queue/{item.id}/decide",
        json={"status": "rejected", "review_notes": "harassment"},
        headers=auth_headers(superuser.id),
    )
    assert response.status_code == 200

    table = sa.table("outreach_messages", sa.column("id", sa.Uuid()), sa.column("admin_blocked"))
    result = await db_session.execute(
        sa.select(table.c.admin_blocked).where(table.c.id == message_id)
    )
    assert bool(result.scalar_one()) is True


async def test_decide_module3_placeholder_does_not_raise(
    client, superuser, db_session, auth_headers
):
    item = await _make_queue_item(db_session, resource_type="practice_audio", resource_id=uuid4())

    response = client.post(
        f"/api/admin/review-queue/{item.id}/decide",
        json={"status": "rejected", "review_notes": "n/a"},
        headers=auth_headers(superuser.id),
    )
    assert response.status_code == 200
