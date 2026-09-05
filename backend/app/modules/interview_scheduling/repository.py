"""Data-access layer for interview scheduling. Workers import this, never service.py."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.interview_scheduling.models import InterviewSchedule


async def upsert_schedule(
    db: AsyncSession,
    *,
    job_match_id: UUID,
    user_id: UUID,
    scheduled_at: datetime,
    duration_minutes: int,
    notes: str | None,
) -> InterviewSchedule:
    """INSERT-or-UPDATE keyed on the job_match_id UNIQUE constraint — this is the
    rescheduling path: a candidate who re-opens the dialog and picks a new time
    updates the existing row (and re-fires §8.5/§8.6's notification+reminder for
    the new time) rather than erroring on the UNIQUE violation or creating a
    second row. Read-then-write, not a raw SQL upsert, since SQLite's
    ON CONFLICT syntax and Postgres's differ enough that a portable two-step
    (SELECT, then INSERT or UPDATE) is clearer than dialect-branching upsert SQL
    for a low-frequency, single-row-per-user operation like this.
    """
    existing = await get_schedule_for_match(db, job_match_id, user_id)
    if existing is not None:
        existing.scheduled_at = scheduled_at
        existing.duration_minutes = duration_minutes
        existing.notes = notes
        existing.reminder_sent_at = None  # rescheduled — the old reminder timer is stale
        await db.flush()
        await db.commit()
        return existing

    schedule = InterviewSchedule(
        job_match_id=job_match_id,
        user_id=user_id,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        notes=notes,
    )
    db.add(schedule)
    await db.flush()
    await db.commit()
    return schedule


async def get_schedule_for_match(
    db: AsyncSession, job_match_id: UUID, user_id: UUID
) -> InterviewSchedule | None:
    result = await db.execute(
        select(InterviewSchedule).where(
            InterviewSchedule.job_match_id == job_match_id,
            InterviewSchedule.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_schedule(db: AsyncSession, schedule_id: UUID) -> None:
    await db.execute(delete(InterviewSchedule).where(InterviewSchedule.id == schedule_id))
    await db.commit()


async def mark_reminder_sent(db: AsyncSession, schedule_id: UUID) -> None:
    """Idempotency guard for the reminder worker task (§8.6) — sets
    reminder_sent_at so a worker retry (RQ retries on transient failure) or a
    duplicate enqueue can never double-send the reminder email/push.
    """
    await db.execute(
        update(InterviewSchedule)
        .where(InterviewSchedule.id == schedule_id, InterviewSchedule.reminder_sent_at.is_(None))
        .values(reminder_sent_at=datetime.now(UTC))
    )
    await db.commit()
