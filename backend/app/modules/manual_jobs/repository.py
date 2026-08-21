"""Data-access layer for manual job entries. Workers import this, never service.py."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_matching.models import JobMatch
from app.modules.manual_jobs.models import ManualJobEntry


async def create_manual_entry(
    db: AsyncSession, user_id: UUID, fields: dict[str, Any]
) -> tuple[ManualJobEntry, JobMatch]:
    """Creates the ManualJobEntry row, then a companion JobMatch row with
    manual_job_entry_id=entry.id, job_posting_id=None, similarity_score=0.0,
    rule_score=0.0, overall_score=0.0, score_breakdown={}, application_status="new"
    (the "no overall_score/similarity for manual entries — nothing to embed
    against" design point from the original research; 0.0 here is a sentinel, not
    a real score — §10.6 covers how the frontend must render it, since 0.0
    displayed literally would misleadingly look like a real terrible-match score
    rather than "not applicable"). Both inserts happen in one transaction — if the
    JobMatch insert fails (e.g. a future constraint violation), the ManualJobEntry
    insert rolls back too, so there's never an orphaned entry with no tracker row.
    """
    entry = ManualJobEntry(user_id=user_id, **fields)
    db.add(entry)
    await db.flush()  # populate entry.id for the FK below, without committing yet

    match = JobMatch(
        user_id=user_id,
        job_posting_id=None,
        manual_job_entry_id=entry.id,
        similarity_score=0.0,
        rule_score=0.0,
        overall_score=0.0,
        score_breakdown={},  # deliberately empty, not {"below_similarity_threshold": True} —
        # that flag (Module A, §5.3) means something specific ("a real similarity
        # search ran and fell back"), which never applies to a manual entry; an
        # empty dict correctly signals "not applicable" rather than overloading
        # the flag with a second meaning
        application_status="new",
    )
    db.add(match)
    await db.flush()
    await db.commit()

    return entry, match
