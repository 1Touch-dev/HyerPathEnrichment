"""Data-access layer for the application tracker. Extends job_matching's list_matches_for_user
with status filter + sort options, and owns the single-flight status UPDATE."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.application_tracker.schemas import _ALL_STATUSES, ApplicationStatus
from app.modules.job_matching.models import JobMatch, JobPosting
from app.modules.job_matching.repository import get_owned_match  # re-exported for

# this module's service.py — Module C never redefines the owned-single-match
# lookup; it imports Module B's get_owned_match (job_matching/repository.py,
# §6.5) directly, same read-only cross-module convention as everywhere else.
from app.modules.manual_jobs.models import ManualJobEntry

__all__ = [
    "count_by_status",
    "get_manual_entries",
    "get_owned_match",
    "list_tracked_matches",
    "update_status",
]

_SORT_COLUMNS: dict[str, Any] = {
    "newest": JobMatch.created_at.desc(),
    "oldest": JobMatch.created_at.asc(),
    # Manual entries (Module F) store a 0.0 sentinel in overall_score (the column
    # is nullable=False, so `.is_(None)` is always False and contributes nothing
    # to the ORDER BY — that sentinel can collide with a real match that
    # legitimately scores 0.0, e.g. via compute_overall_score's clamp). Tie-break
    # on `job_posting_id IS NULL` instead (True only for manual entries, per the
    # ck_job_matches_exactly_one_source invariant — same manual-entry check used
    # in job_matching/repository.py's join logic), so manual entries always sort
    # last regardless of dialect NULL-ordering or a 0.0/0.0 sentinel collision.
    "score": (JobMatch.job_posting_id.is_(None), JobMatch.overall_score.desc()),
    "recently_updated": (
        JobMatch.status_updated_at.is_(None),
        JobMatch.status_updated_at.desc(),
        JobMatch.created_at.desc(),  # tie-break for rows never manually updated
    ),
}


async def list_tracked_matches(
    db: AsyncSession,
    user_id: UUID,
    *,
    status: ApplicationStatus | None,
    sort: Literal["newest", "oldest", "score", "recently_updated"],
    limit: int,
    offset: int,
) -> tuple[list[tuple[JobMatch, JobPosting | None]], int]:
    """Extends job_matching's list_matches_for_user with status filter + sort options.
    Deliberately NOT added to job_matching/repository.py itself (see §7.4 rationale).

    Uses outerjoin (not join) from day one — Module F (§10) later widens
    JobMatch.job_posting_id to nullable for manual entries; building this query
    with an inner join now would mean silently dropping every manual-entry row
    the moment Module F ships, with no error surfaced anywhere. Cheaper to write
    the correct join shape once than to remember to revisit this file later.
    """
    order_by = _SORT_COLUMNS[sort]
    order_clauses = order_by if isinstance(order_by, tuple) else (order_by,)

    stmt = (
        select(JobMatch, JobPosting)
        .outerjoin(JobPosting, JobMatch.job_posting_id == JobPosting.id)
        .where(JobMatch.user_id == user_id)
    )
    if status is not None:
        stmt = stmt.where(JobMatch.application_status == status)
    stmt = stmt.order_by(*order_clauses).limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = [(m, p) for m, p in result.all()]

    count_stmt = select(func.count()).select_from(JobMatch).where(JobMatch.user_id == user_id)
    if status is not None:
        count_stmt = count_stmt.where(JobMatch.application_status == status)
    total = (await db.execute(count_stmt)).scalar_one()

    return rows, total


async def update_status(
    db: AsyncSession, match_id: UUID, user_id: UUID, new_status: ApplicationStatus
) -> JobMatch | None:
    """Single-flight UPDATE (not read-then-write) so two concurrent PATCHes from
    the same candidate (e.g. a double-click before the button disables, or two
    browser tabs) can never race into an inconsistent read-modify-write — the
    UPDATE...WHERE is atomic at the database level regardless of how many
    concurrent requests hit it, and RETURNING gives us the fresh row in the same
    round-trip.
    """
    result = await db.execute(
        update(JobMatch)
        .where(JobMatch.id == match_id, JobMatch.user_id == user_id)
        .values(application_status=new_status, status_updated_at=datetime.now(UTC))
        .returning(JobMatch)
    )
    row = result.first()
    if row is None:
        return None
    await db.commit()
    match: JobMatch = row[0]
    return match


async def count_by_status(db: AsyncSession, user_id: UUID) -> dict[str, int]:
    """One GROUP BY query for the tab/column badge counts — avoids 6 separate
    COUNT(*) round-trips from the frontend rendering 6 status tabs. Zero-fills
    every status not present in the result (a candidate with no rejected
    applications yet must see rejected: 0, not a missing key the frontend has
    to guard against with `?? 0` at every call site).
    """
    result = await db.execute(
        select(JobMatch.application_status, func.count())
        .where(JobMatch.user_id == user_id)
        .group_by(JobMatch.application_status)
    )
    counts: dict[str, int] = {status: 0 for status in _ALL_STATUSES}
    counts.update({row[0]: row[1] for row in result.all()})
    return counts


async def get_manual_entries(db: AsyncSession, ids: list[UUID]) -> dict[UUID, ManualJobEntry]:
    """Batch-fetch ManualJobEntry rows by id, keyed for easy lookup.

    `list_tracked_matches` above already outer-joins JobPosting so manual-entry
    rows (job_posting_id IS NULL) are never silently dropped from the tracker —
    per §10.6, this IS the one place manual entries are supposed to show up. But
    its response mapping still needs each manual entry's own title/company/
    location/source_url (JobMatch itself carries none of those), hence this
    second, deliberately separate lookup rather than widening the tracker query's
    join further — keeps list_tracked_matches' SQL shape unchanged for the common
    (non-manual) case, batches the manual-entry side into one extra query instead
    of N+1.
    """
    if not ids:
        return {}
    result = await db.execute(select(ManualJobEntry).where(ManualJobEntry.id.in_(ids)))
    return {entry.id: entry for entry in result.scalars().all()}
