"""Admin read-only visibility into candidate swipe actions (`job_swipe:read`).

Swipe/match records are interaction data, not published content (see
migration 041 — only `job_swipe:read` is seeded, deliberately no
`job_swipe:moderate`). This router is intentionally read-only: no
moderate/mutate endpoint exists here, and none should be added."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin.pagination import decode_cursor, encode_cursor
from app.modules.admin.permissions import require_permission
from app.modules.job_matching.models import JobMatch, JobPosting
from app.modules.job_swipe.models import JobSwipeAction

router = APIRouter(prefix="/api/admin/job-swipe", tags=["admin"], route_class=EnvelopeAPIRoute)


class JobSwipeActionResponse(BaseModel):
    """A swipe action joined with its job-posting context, for admin visibility."""

    id: UUID
    job_match_id: UUID
    user_id: UUID
    direction: str
    created_at: datetime
    job_posting_id: UUID | None
    job_posting_title: str | None
    job_posting_company: str | None


class JobSwipeActionListResponse(BaseModel):
    items: list[JobSwipeActionResponse]
    next_cursor: str | None
    has_more: bool


def _joined_query() -> Select[Any]:
    """`JobSwipeAction` outer-joined to `JobMatch`/`JobPosting` for title/company
    context. Outer join (not inner) so a swipe row is still visible to admins
    even if its match/posting linkage is ever missing, matching this module's
    fail-soft-over-raising convention (see e.g. `SystemHealthResponse`)."""
    return (
        select(
            JobSwipeAction.id,
            JobSwipeAction.job_match_id,
            JobSwipeAction.user_id,
            JobSwipeAction.direction,
            JobSwipeAction.created_at,
            JobPosting.id.label("job_posting_id"),
            JobPosting.title.label("job_posting_title"),
            JobPosting.company.label("job_posting_company"),
        )
        .outerjoin(JobMatch, JobMatch.id == JobSwipeAction.job_match_id)
        .outerjoin(JobPosting, JobPosting.id == JobMatch.job_posting_id)
    )


def _row_to_response(row: object) -> JobSwipeActionResponse:
    return JobSwipeActionResponse(
        id=row.id,  # type: ignore[attr-defined]
        job_match_id=row.job_match_id,  # type: ignore[attr-defined]
        user_id=row.user_id,  # type: ignore[attr-defined]
        direction=row.direction,  # type: ignore[attr-defined]
        created_at=row.created_at,  # type: ignore[attr-defined]
        job_posting_id=row.job_posting_id,  # type: ignore[attr-defined]
        job_posting_title=row.job_posting_title,  # type: ignore[attr-defined]
        job_posting_company=row.job_posting_company,  # type: ignore[attr-defined]
    )


@router.get("", response_model=JobSwipeActionListResponse)
async def list_job_swipe_actions(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    direction: Literal["right", "left", "up"] | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    _user: User = Depends(require_permission("job_swipe", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> JobSwipeActionListResponse:
    query = _joined_query().order_by(JobSwipeAction.created_at.desc(), JobSwipeAction.id.desc())
    if direction is not None:
        query = query.where(JobSwipeAction.direction == direction)
    if user_id is not None:
        query = query.where(JobSwipeAction.user_id == user_id)
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (JobSwipeAction.created_at < created_at)
            | ((JobSwipeAction.created_at == created_at) & (JobSwipeAction.id < UUID(entity_id)))
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_response(row) for row in rows]
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return JobSwipeActionListResponse(items=items, next_cursor=next_cursor, has_more=has_more)


@router.get("/{swipe_action_id}", response_model=JobSwipeActionResponse)
async def get_job_swipe_action(
    swipe_action_id: UUID,
    _user: User = Depends(require_permission("job_swipe", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> JobSwipeActionResponse:
    query = _joined_query().where(JobSwipeAction.id == swipe_action_id)
    row = (await db.execute(query)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Swipe action not found")
    return _row_to_response(row)
