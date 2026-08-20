"""Business logic for the application tracker: mapping JobMatch rows to tracked responses."""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.modules.application_tracker import repository
from app.modules.application_tracker.repository import get_owned_match
from app.modules.application_tracker.schemas import (
    ApplicationStatus,
    TrackedMatchListResponse,
    TrackedMatchResponse,
)
from app.modules.job_matching.models import JobMatch, JobPosting


def _to_tracked_response(match: JobMatch, posting: JobPosting | None) -> TrackedMatchResponse:
    return TrackedMatchResponse(
        match_id=str(match.id),
        job_posting_id=str(match.job_posting_id) if match.job_posting_id else "",
        title=posting.title if posting else "",
        company=posting.company if posting else "",
        location=posting.location if posting else None,
        remote=posting.remote if posting else False,
        source_url=posting.source_url if posting else None,
        overall_score=match.overall_score if posting is not None else None,  # sentinel-hiding
        application_status=cast("ApplicationStatus", match.application_status),
        apply_clicked_at=match.apply_clicked_at,
        applied_at=match.applied_at,
        status_updated_at=match.status_updated_at,
        created_at=match.created_at,
        next_interview_at=None,  # populated by a follow-up outerjoin against
        # InterviewSchedule once Module D lands; None until then
    )


async def list_tracked(
    db: AsyncSession,
    user_id: UUID,
    *,
    status: ApplicationStatus | None,
    sort: Literal["newest", "oldest", "score", "recently_updated"],
    limit: int,
    offset: int,
) -> TrackedMatchListResponse:
    rows, total = await repository.list_tracked_matches(
        db, user_id, status=status, sort=sort, limit=limit, offset=offset
    )
    counts = await repository.count_by_status(db, user_id)
    return TrackedMatchListResponse(
        matches=[_to_tracked_response(m, p) for m, p in rows],
        total=total,
        limit=limit,
        offset=offset,
        counts_by_status=cast("dict[ApplicationStatus, int]", counts),
    )


async def update_status(
    db: AsyncSession, user_id: UUID, match_id: UUID, new_status: ApplicationStatus
) -> TrackedMatchResponse:
    match = await repository.update_status(db, match_id, user_id, new_status)
    if match is None:
        raise NotFoundError("Match not found")
    owned = await get_owned_match(db, match_id, user_id)
    assert (
        owned is not None
    )  # match row is guaranteed present here since update_status just returned it
    _, posting = owned
    return _to_tracked_response(match, posting)
