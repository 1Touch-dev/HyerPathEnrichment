"""Data-access layer for job_swipe. Reads Module 1's JobMatch/JobPosting tables directly (read-only)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# NOTE: JobMatch / JobPosting come from Module 1 (phase2_module1.md §7.2) — imported
# here, never redefined. This import will fail with ModuleNotFoundError until
# Module 1 is implemented; see §4.1's explicit cross-module dependency note.
from app.modules.job_matching.models import JobMatch, JobPosting
from app.modules.job_swipe.models import JobSwipeAction


async def get_unswiped_matches(
    db: AsyncSession, user_id: UUID, limit: int
) -> list[tuple[JobMatch, JobPosting]]:
    already_swiped = select(JobSwipeAction.job_match_id).where(JobSwipeAction.user_id == user_id)
    result = await db.execute(
        select(JobMatch, JobPosting)
        .join(JobPosting, JobMatch.job_posting_id == JobPosting.id)
        .where(JobMatch.user_id == user_id, JobMatch.id.not_in(already_swiped))
        .order_by(JobMatch.overall_score.desc())
        .limit(limit)
    )
    return [(m, p) for m, p in result.all()]


async def record_swipe(
    db: AsyncSession, job_match_id: UUID, user_id: UUID, direction: str
) -> JobSwipeAction:
    existing = await db.execute(
        select(JobSwipeAction).where(JobSwipeAction.job_match_id == job_match_id)
    )
    action = existing.scalar_one_or_none()
    if action:
        action.direction = direction
        action.created_at = datetime.now(UTC)
    else:
        from uuid import uuid4

        action = JobSwipeAction(
            id=uuid4(), job_match_id=job_match_id, user_id=user_id, direction=direction
        )
        db.add(action)
    await db.commit()
    await db.refresh(action)
    return action
