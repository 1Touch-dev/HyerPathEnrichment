"""Admin moderation of manually-added job entries: list/detail/moderate
(soft-delete/restore) + RBAC gate + audit-log assertions (migration 046,
Admin Module — Module 4 admin visibility/moderation surface). Mirrors
`test_admin_job_postings_moderation.py`'s coverage style, adapted for
`ManualJobEntry.deleted_at`'s soft-delete toggle (same convention as
`documents_router.py`)."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.core.logging import scrub_sensitive_data
from tests.envelope_helpers import assert_error, assert_success


def _idempotency_headers(auth_headers, user_id, key: str):
    return {**auth_headers(user_id), "Idempotency-Key": key}


async def _make_manual_job_entry(db_session, user_id, /, **overrides):
    from app.modules.manual_jobs.models import ManualJobEntry

    suffix = uuid4().hex[:8]
    defaults = {
        "user_id": user_id,
        "title": f"Manual Role {suffix}",
        "company": f"Manual Co {suffix}",
        "location": "Remote",
        "source_label": "Referral",
        "source_url": "https://example.com/job",
        "notes": "Found via a friend",
    }
    defaults.update(overrides)
    entry = ManualJobEntry(**defaults)
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


async def test_list_manual_job_entries_requires_authentication(client):
    response = client.get("/api/admin/manual-job-entries")
    assert response.status_code == 401


async def test_list_manual_job_entries_regular_user_forbidden(client, regular_user, auth_headers):
    response = client.get("/api/admin/manual-job-entries", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


async def test_list_manual_job_entries_returns_cursor_shape(
    client, superuser, auth_headers, db_session, regular_user
):
    await _make_manual_job_entry(db_session, regular_user.id)
    response = client.get("/api/admin/manual-job-entries", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert "items" in body and "next_cursor" in body and "has_more" in body
    assert len(body["items"]) >= 1


async def test_list_manual_job_entries_filters_by_deleted(
    client, superuser, auth_headers, db_session, regular_user
):
    from datetime import UTC, datetime

    active = await _make_manual_job_entry(db_session, regular_user.id)
    deleted = await _make_manual_job_entry(
        db_session, regular_user.id, deleted_at=datetime.now(UTC)
    )

    response = client.get(
        "/api/admin/manual-job-entries",
        params={"deleted": True},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    ids = {item["id"] for item in body["items"]}
    assert str(deleted.id) in ids
    assert str(active.id) not in ids


async def test_get_manual_job_entry_detail(
    client, superuser, auth_headers, db_session, regular_user
):
    entry = await _make_manual_job_entry(db_session, regular_user.id)
    response = client.get(
        f"/api/admin/manual-job-entries/{entry.id}", headers=auth_headers(superuser.id)
    )
    body = assert_success(response)
    assert body["id"] == str(entry.id)
    assert body["deleted_at"] is None


async def test_get_manual_job_entry_detail_404(client, superuser, auth_headers):
    response = client.get(
        f"/api/admin/manual-job-entries/{uuid4()}", headers=auth_headers(superuser.id)
    )
    assert_error(response, 404)


async def test_moderate_manual_job_entry_happy_path(
    client, superuser, auth_headers, db_session, regular_user
):
    from app.modules.admin.models import AdminAuditLog

    entry = await _make_manual_job_entry(db_session, regular_user.id)

    response = client.post(
        f"/api/admin/manual-job-entries/{entry.id}/moderate",
        json={"action": "soft_delete", "reason": "Duplicate entry reported"},
        headers=_idempotency_headers(auth_headers, superuser.id, f"manual-job-delete-{entry.id}"),
    )
    body = assert_success(response)
    assert body["deleted_at"] is not None

    await db_session.refresh(entry)
    assert entry.deleted_at is not None

    result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "manual_job_entries.moderate",
            AdminAuditLog.target_id == str(entry.id),
        )
    )
    log_entry = result.scalar_one()
    assert log_entry.actor_user_id == superuser.id
    assert log_entry.target_type == "manual_job_entry"
    deleted_at_key = next(iter(scrub_sensitive_data({"deleted_at": None})))
    reason_key = next(iter(scrub_sensitive_data({"reason": None})))
    assert log_entry.before[deleted_at_key] is None
    assert log_entry.after[deleted_at_key] is not None
    assert log_entry.after[reason_key] == "Duplicate entry reported"


async def test_moderate_manual_job_entry_restore(
    client, superuser, auth_headers, db_session, regular_user
):
    from datetime import UTC, datetime

    entry = await _make_manual_job_entry(db_session, regular_user.id, deleted_at=datetime.now(UTC))

    response = client.post(
        f"/api/admin/manual-job-entries/{entry.id}/moderate",
        json={"action": "restore", "reason": None},
        headers=_idempotency_headers(auth_headers, superuser.id, f"manual-job-restore-{entry.id}"),
    )
    body = assert_success(response)
    assert body["deleted_at"] is None

    await db_session.refresh(entry)
    assert entry.deleted_at is None


async def test_moderate_manual_job_entry_404(client, superuser, auth_headers):
    response = client.post(
        f"/api/admin/manual-job-entries/{uuid4()}/moderate",
        json={"action": "soft_delete", "reason": None},
        headers=_idempotency_headers(auth_headers, superuser.id, "manual-job-missing"),
    )
    assert_error(response, 404)


async def test_moderate_manual_job_entry_requires_moderate_permission_for_regular_user(
    client, regular_user, auth_headers, db_session
):
    entry = await _make_manual_job_entry(db_session, regular_user.id)
    response = client.post(
        f"/api/admin/manual-job-entries/{entry.id}/moderate",
        json={"action": "soft_delete", "reason": None},
        headers=_idempotency_headers(auth_headers, regular_user.id, "manual-job-forbidden"),
    )
    assert_error(response, 403)


async def test_support_role_can_read_but_not_moderate(
    client, support_user, auth_headers, db_session, regular_user
):
    """migration 046 grants 'support' manual_job_entries:read but NOT
    manual_job_entries:moderate."""
    entry = await _make_manual_job_entry(db_session, regular_user.id)

    list_response = client.get(
        "/api/admin/manual-job-entries", headers=auth_headers(support_user.id)
    )
    assert_success(list_response)

    detail_response = client.get(
        f"/api/admin/manual-job-entries/{entry.id}", headers=auth_headers(support_user.id)
    )
    assert_success(detail_response)

    moderate_response = client.post(
        f"/api/admin/manual-job-entries/{entry.id}/moderate",
        json={"action": "soft_delete", "reason": None},
        headers=_idempotency_headers(auth_headers, support_user.id, "manual-job-support-forbidden"),
    )
    assert_error(moderate_response, 403)


async def test_moderate_manual_job_entry_requires_idempotency_key(
    client, superuser, auth_headers, db_session, regular_user
):
    entry = await _make_manual_job_entry(db_session, regular_user.id)
    response = client.post(
        f"/api/admin/manual-job-entries/{entry.id}/moderate",
        json={"action": "soft_delete", "reason": "Duplicate entry reported"},
        headers=auth_headers(superuser.id),
    )
    assert_error(response, 400)
