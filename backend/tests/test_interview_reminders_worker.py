"""Tests for app.workers.tasks.interview_reminders (RQ worker entrypoint, Module 4,
Module D §8.9).

`send_interview_reminder_job` is a *sync* function that internally calls
`asyncio.run(...)`. Calling `asyncio.run()` from inside an already-running event
loop raises `RuntimeError`, so these tests are deliberately plain sync
`test_...` functions (no `@pytest.mark.asyncio`, no `db` fixture) — each worker
call gets to create and fully tear down its own event loop, exactly like it
does in production under RQ. Setup/assertions use `SyncSessionLocal`, same
convention as `test_job_matching_worker.py`.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.auth.models import User
from app.database.session import SyncSessionLocal
from app.database.session import engine as _async_engine
from app.modules.interview_scheduling.models import InterviewSchedule
from app.modules.job_matching.models import JobMatch, JobPosting, PushSubscription
from app.workers.tasks.interview_reminders import send_interview_reminder_job


@pytest.fixture(autouse=True)
def _isolate_async_engine_per_test():
    """Dispose the shared async engine's connection pool before/after each test.

    `send_interview_reminder_job` wraps `asyncio.run(...)` and explicitly disposes
    `engine` in its own `finally` block, same as `_scan_jobs_for_candidate_async` —
    a pooled aiosqlite connection created under one `asyncio.run()` event loop must
    never be reused by a different `asyncio.run()` event loop.
    """
    asyncio.run(_async_engine.dispose())
    yield
    asyncio.run(_async_engine.dispose())


def _mock_send_template(return_value: bool = True):
    """Patch `EmailService.send_template` — same rationale as
    `test_job_matching_worker.py`'s `_mock_enqueue_email`: patch where the call
    actually resolves so both `get_email_service().send_template(...)` call
    sites (the router and this worker task) are covered by one patch target.
    """
    return patch(
        "app.services.email_service.EmailService.send_template",
        new_callable=AsyncMock,
        return_value=return_value,
    )


def _mock_send_push_notification(return_value: bool = True):
    return patch(
        "app.modules.job_matching.push.send_push_notification",
        new_callable=AsyncMock,
        return_value=return_value,
    )


def _create_user(**overrides) -> User:
    with SyncSessionLocal() as session:
        fields = {
            "email": f"interview-reminder-worker-{uuid.uuid4().hex[:10]}@example.com",
            "first_name": "Worker",
            "last_name": "Candidate",
            "is_verified": True,
        }
        fields.update(overrides)
        user = User(**fields)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def _create_match(user: User, **posting_overrides) -> tuple[JobMatch, JobPosting]:
    with SyncSessionLocal() as session:
        posting_fields = {
            "dedup_key": f"dedup-{uuid.uuid4().hex}",
            "title": "Backend Engineer",
            "company": "Acme Corp",
            "location": "Remote",
            "remote": True,
            "source": "linkedin",
            "source_url": "https://example.com/jobs/1",
        }
        posting_fields.update(posting_overrides)
        posting = JobPosting(**posting_fields)
        session.add(posting)
        session.commit()
        session.refresh(posting)

        match = JobMatch(
            user_id=user.id,
            job_posting_id=posting.id,
            similarity_score=0.9,
            rule_score=0.8,
            overall_score=86.0,
            score_breakdown={},
        )
        session.add(match)
        session.commit()
        session.refresh(match)
        return match, posting


def _create_schedule(
    user: User, match: JobMatch, *, scheduled_at: datetime, reminder_sent_at: datetime | None = None
) -> InterviewSchedule:
    with SyncSessionLocal() as session:
        schedule = InterviewSchedule(
            job_match_id=match.id,
            user_id=user.id,
            scheduled_at=scheduled_at,
            duration_minutes=60,
            notes="Bring resume",
            reminder_sent_at=reminder_sent_at,
        )
        session.add(schedule)
        session.commit()
        session.refresh(schedule)
        return schedule


def _fetch_schedule(schedule_id) -> InterviewSchedule | None:
    with SyncSessionLocal() as session:
        return session.get(InterviewSchedule, schedule_id)


# ---------------------------------------------------------------------------
# send_interview_reminder_job
# ---------------------------------------------------------------------------


def _parse_ctx_datetime(value: str) -> datetime:
    """SQLite (used for local/CI tests) drops tzinfo on read-back — normalize
    to UTC-aware before comparing against a UTC-aware expectation, same
    convention `test_email_verification.py`/`test_account_deletion.py` already use.
    """
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def test_reminder_sends_email_and_marks_sent() -> None:
    user = _create_user()
    match, posting = _create_match(user)
    scheduled_at = datetime.now(UTC) + timedelta(hours=20)
    schedule = _create_schedule(user, match, scheduled_at=scheduled_at)

    with _mock_send_template() as mock_send_template:
        send_interview_reminder_job(str(schedule.id))

    mock_send_template.assert_called_once()
    call_args = mock_send_template.call_args
    assert call_args.args[0].value == "interview_reminder"
    assert call_args.kwargs["recipient"] == user.email
    ctx = call_args.kwargs["context"]
    assert ctx["title"] == posting.title
    assert ctx["company"] == posting.company
    assert _parse_ctx_datetime(ctx["scheduled_at"]) == scheduled_at

    refreshed = _fetch_schedule(schedule.id)
    assert refreshed is not None
    assert refreshed.reminder_sent_at is not None


def test_reminder_idempotency_guard_skips_if_already_sent() -> None:
    """A schedule that already has `reminder_sent_at` set (e.g. an RQ retry, or a
    duplicate enqueue) must never send a second reminder."""
    user = _create_user()
    match, _posting = _create_match(user)
    scheduled_at = datetime.now(UTC) + timedelta(hours=20)
    already_sent_at = datetime.now(UTC) - timedelta(hours=1)
    schedule = _create_schedule(
        user, match, scheduled_at=scheduled_at, reminder_sent_at=already_sent_at
    )

    with _mock_send_template() as mock_send_template:
        send_interview_reminder_job(str(schedule.id))

    mock_send_template.assert_not_called()

    refreshed = _fetch_schedule(schedule.id)
    assert refreshed is not None
    # reminder_sent_at is untouched — not bumped to "now" by a skipped run.
    assert _parse_ctx_datetime(refreshed.reminder_sent_at.isoformat()) == already_sent_at


def test_reminder_uses_current_scheduled_at_not_stale_snapshot() -> None:
    """The interview is rescheduled to a new time *after* the reminder job was
    enqueued but *before* it runs — the reminder must reflect the new time, not
    whatever `scheduled_at` looked like at enqueue time (§8.6)."""
    user = _create_user()
    match, posting = _create_match(user)
    original_scheduled_at = datetime.now(UTC) + timedelta(hours=20)
    schedule = _create_schedule(user, match, scheduled_at=original_scheduled_at)

    new_scheduled_at = datetime.now(UTC) + timedelta(hours=48)
    with SyncSessionLocal() as session:
        row = session.get(InterviewSchedule, schedule.id)
        assert row is not None
        row.scheduled_at = new_scheduled_at
        session.commit()

    with _mock_send_template() as mock_send_template:
        send_interview_reminder_job(str(schedule.id))

    ctx = mock_send_template.call_args.kwargs["context"]
    assert _parse_ctx_datetime(ctx["scheduled_at"]) == new_scheduled_at
    assert ctx["scheduled_at"] != original_scheduled_at.isoformat()
    assert ctx["title"] == posting.title


def test_reminder_sends_push_to_all_registered_subscriptions() -> None:
    user = _create_user()
    match, _posting = _create_match(user)
    schedule = _create_schedule(user, match, scheduled_at=datetime.now(UTC) + timedelta(hours=20))

    with SyncSessionLocal() as session:
        for _ in range(2):
            session.add(
                PushSubscription(
                    user_id=user.id,
                    endpoint=f"https://push.example.com/{uuid.uuid4().hex}",
                    p256dh_key="p256dh",
                    auth_key="auth",
                )
            )
        session.commit()

    with _mock_send_template(), _mock_send_push_notification() as mock_push:
        send_interview_reminder_job(str(schedule.id))

    assert mock_push.call_count == 2


def test_reminder_no_op_when_schedule_no_longer_exists() -> None:
    """The interview was cancelled between enqueue and this job running — the
    row is gone, so the reminder is skipped rather than erroring."""
    with _mock_send_template() as mock_send_template:
        send_interview_reminder_job(str(uuid.uuid4()))

    mock_send_template.assert_not_called()
