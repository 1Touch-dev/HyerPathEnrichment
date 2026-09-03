"""Admin moderation of interview schedules: list/detail/moderate (soft
cancel/restore) + RBAC gate + audit-log assertions (migration 046, Admin
Module — Module 4 admin visibility/moderation surface)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.logging import scrub_sensitive_data
from tests.envelope_helpers import assert_error, assert_success


@pytest.fixture(autouse=True)
def _mock_interview_reminder_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same convention as `test_interview_scheduling_router.py`: mock the RQ/
    rq-scheduler call site directly rather than routing through `FakeRedis`."""
    monkeypatch.setattr("app.workers.queue.cancel_interview_reminder", MagicMock())


async def _make_job_match(db_session, user_id, /, **overrides):
    from app.modules.job_matching.models import JobMatch, JobPosting

    suffix = uuid4().hex[:8]
    posting = JobPosting(
        dedup_key=f"dedup-{suffix}",
        title=f"Backend Engineer {suffix}",
        company=f"Acme Corp {suffix}",
        source="linkedin",
    )
    db_session.add(posting)
    await db_session.commit()
    await db_session.refresh(posting)

    defaults = {
        "user_id": user_id,
        "job_posting_id": posting.id,
        "similarity_score": 0.8,
        "rule_score": 0.7,
        "overall_score": 75.0,
    }
    defaults.update(overrides)
    match = JobMatch(**defaults)
    db_session.add(match)
    await db_session.commit()
    await db_session.refresh(match)
    return match


async def _make_interview_schedule(db_session, user_id, /, **overrides):
    from app.modules.interview_scheduling.models import InterviewSchedule

    match = await _make_job_match(db_session, user_id)
    defaults = {
        "job_match_id": match.id,
        "user_id": user_id,
        "scheduled_at": datetime.now(UTC) + timedelta(days=1),
        "duration_minutes": 60,
    }
    defaults.update(overrides)
    schedule = InterviewSchedule(**defaults)
    db_session.add(schedule)
    await db_session.commit()
    await db_session.refresh(schedule)
    return schedule


async def test_list_interview_schedules_requires_authentication(client):
    response = client.get("/api/admin/interview-schedules")
    assert response.status_code == 401


async def test_list_interview_schedules_regular_user_forbidden(client, regular_user, auth_headers):
    response = client.get("/api/admin/interview-schedules", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


async def test_list_interview_schedules_returns_cursor_shape(
    client, superuser, auth_headers, db_session, regular_user
):
    await _make_interview_schedule(db_session, regular_user.id)
    response = client.get("/api/admin/interview-schedules", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert "items" in body and "next_cursor" in body and "has_more" in body
    assert len(body["items"]) >= 1


async def test_list_interview_schedules_filters_by_admin_cancelled(
    client, superuser, auth_headers, db_session, regular_user
):
    active = await _make_interview_schedule(db_session, regular_user.id)
    cancelled = await _make_interview_schedule(
        db_session,
        regular_user.id,
        admin_cancelled_at=datetime.now(UTC),
        admin_cancelled_by=superuser.id,
    )

    response = client.get(
        "/api/admin/interview-schedules",
        params={"admin_cancelled": True},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    ids = {item["id"] for item in body["items"]}
    assert str(cancelled.id) in ids
    assert str(active.id) not in ids


async def test_get_interview_schedule_detail(
    client, superuser, auth_headers, db_session, regular_user
):
    schedule = await _make_interview_schedule(db_session, regular_user.id)
    response = client.get(
        f"/api/admin/interview-schedules/{schedule.id}", headers=auth_headers(superuser.id)
    )
    body = assert_success(response)
    assert body["id"] == str(schedule.id)
    assert body["admin_cancelled_at"] is None


async def test_get_interview_schedule_detail_404(client, superuser, auth_headers):
    response = client.get(
        f"/api/admin/interview-schedules/{uuid4()}", headers=auth_headers(superuser.id)
    )
    assert_error(response, 404)


async def test_moderate_interview_schedule_cancel_happy_path(
    client, superuser, auth_headers, db_session, regular_user
):
    from app.modules.admin.models import AdminAuditLog
    from app.workers import queue

    schedule = await _make_interview_schedule(db_session, regular_user.id)

    response = client.post(
        f"/api/admin/interview-schedules/{schedule.id}/moderate",
        json={"action": "cancel", "reason": "Candidate reported no-show by employer"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert body["admin_cancelled_at"] is not None
    assert body["admin_cancelled_by"] == str(superuser.id)
    queue.cancel_interview_reminder.assert_called_once_with(str(schedule.id))

    await db_session.refresh(schedule)
    assert schedule.admin_cancelled_at is not None
    assert schedule.admin_cancelled_by == superuser.id

    result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "interview_schedules.moderate",
            AdminAuditLog.target_id == str(schedule.id),
        )
    )
    entry = result.scalar_one()
    assert entry.actor_user_id == superuser.id
    assert entry.target_type == "interview_schedule"
    cancelled_at_key = next(iter(scrub_sensitive_data({"admin_cancelled_at": None})))
    reason_key = next(iter(scrub_sensitive_data({"reason": None})))
    assert entry.before[cancelled_at_key] is None
    assert entry.after[cancelled_at_key] is not None
    assert entry.after[reason_key] == "Candidate reported no-show by employer"


async def test_moderate_interview_schedule_restore(
    client, superuser, auth_headers, db_session, regular_user
):
    schedule = await _make_interview_schedule(
        db_session,
        regular_user.id,
        admin_cancelled_at=datetime.now(UTC),
        admin_cancelled_by=superuser.id,
    )

    response = client.post(
        f"/api/admin/interview-schedules/{schedule.id}/moderate",
        json={"action": "restore", "reason": None},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert body["admin_cancelled_at"] is None
    assert body["admin_cancelled_by"] is None

    await db_session.refresh(schedule)
    assert schedule.admin_cancelled_at is None
    assert schedule.admin_cancelled_by is None


async def test_moderate_interview_schedule_404(client, superuser, auth_headers):
    response = client.post(
        f"/api/admin/interview-schedules/{uuid4()}/moderate",
        json={"action": "cancel", "reason": None},
        headers=auth_headers(superuser.id),
    )
    assert_error(response, 404)


async def test_moderate_interview_schedule_requires_moderate_permission_for_regular_user(
    client, regular_user, auth_headers, db_session
):
    schedule = await _make_interview_schedule(db_session, regular_user.id)
    response = client.post(
        f"/api/admin/interview-schedules/{schedule.id}/moderate",
        json={"action": "cancel", "reason": None},
        headers=auth_headers(regular_user.id),
    )
    assert_error(response, 403)


async def test_support_role_can_read_but_not_moderate(
    client, support_user, auth_headers, db_session, regular_user
):
    """migration 046 grants 'support' interview_schedules:read but NOT
    interview_schedules:moderate."""
    schedule = await _make_interview_schedule(db_session, regular_user.id)

    list_response = client.get(
        "/api/admin/interview-schedules", headers=auth_headers(support_user.id)
    )
    assert_success(list_response)

    detail_response = client.get(
        f"/api/admin/interview-schedules/{schedule.id}", headers=auth_headers(support_user.id)
    )
    assert_success(detail_response)

    moderate_response = client.post(
        f"/api/admin/interview-schedules/{schedule.id}/moderate",
        json={"action": "cancel", "reason": None},
        headers=auth_headers(support_user.id),
    )
    assert_error(moderate_response, 403)
