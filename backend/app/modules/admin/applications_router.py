"""Admin read-only visibility into candidate job-application-lifecycle status
(`applications:read`, migration 046).

Intentionally read-only: no moderate/mutate endpoint exists here, and none
should be added — `JobMatch.application_status` is user-authored
self-reporting (a candidate's own record of where they are in their job
search), not published/moderatable content, mirroring `job_swipe_router.py`'s
"intentionally read-only" design for the same reason (interaction/self-report
data rather than content someone else needs to police)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
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

router = APIRouter(prefix="/api/admin/applications", tags=["admin"], route_class=EnvelopeAPIRoute)


class AdminApplicationResponse(BaseModel):
    id: UUID
    user_id: UUID
    job_posting_id: UUID | None
    job_posting_title: str | None
    job_posting_company: str | None
    manual_job_entry_id: UUID | None
    application_status: str
    status_updated_at: datetime | None
    apply_clicked_at: datetime | None
    applied_at: datetime | None
    created_at: datetime


class AdminApplicationListResponse(BaseModel):
    items: list[AdminApplicationResponse]
    next_cursor: str | None
    has_more: bool


def _joined_query() -> Select[Any]:
    """`JobMatch` outer-joined to `JobPosting` for title/company context.
    Outer join (not inner) since `job_posting_id` is nullable — a manually
    added job has no `JobPosting` row (see `manual_job_entry_id`)."""
    return select(
        JobMatch.id,
        JobMatch.user_id,
        JobMatch.job_posting_id,
        JobPosting.title.label("job_posting_title"),
        JobPosting.company.label("job_posting_company"),
        JobMatch.manual_job_entry_id,
        JobMatch.application_status,
        JobMatch.status_updated_at,
        JobMatch.apply_clicked_at,
        JobMatch.applied_at,
        JobMatch.created_at,
    ).outerjoin(JobPosting, JobPosting.id == JobMatch.job_posting_id)


def _row_to_response(row: object) -> AdminApplicationResponse:
    return AdminApplicationResponse(
        id=row.id,  # type: ignore[attr-defined]
        user_id=row.user_id,  # type: ignore[attr-defined]
        job_posting_id=row.job_posting_id,  # type: ignore[attr-defined]
        job_posting_title=row.job_posting_title,  # type: ignore[attr-defined]
        job_posting_company=row.job_posting_company,  # type: ignore[attr-defined]
        manual_job_entry_id=row.manual_job_entry_id,  # type: ignore[attr-defined]
        application_status=row.application_status,  # type: ignore[attr-defined]
        status_updated_at=row.status_updated_at,  # type: ignore[attr-defined]
        apply_clicked_at=row.apply_clicked_at,  # type: ignore[attr-defined]
        applied_at=row.applied_at,  # type: ignore[attr-defined]
        created_at=row.created_at,  # type: ignore[attr-defined]
    )


@router.get("", response_model=AdminApplicationListResponse)
async def list_applications(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    application_status: str | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    _user: User = Depends(require_permission("applications", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminApplicationListResponse:
    query = _joined_query().order_by(JobMatch.created_at.desc(), JobMatch.id.desc())
    if application_status is not None:
        query = query.where(JobMatch.application_status == application_status)
    if user_id is not None:
        query = query.where(JobMatch.user_id == user_id)
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (JobMatch.created_at < created_at)
            | ((JobMatch.created_at == created_at) & (JobMatch.id < UUID(entity_id)))
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_response(row) for row in rows]
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return AdminApplicationListResponse(items=items, next_cursor=next_cursor, has_more=has_more)


@router.get("/{job_match_id}", response_model=AdminApplicationResponse)
async def get_application(
    job_match_id: UUID,
    _user: User = Depends(require_permission("applications", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminApplicationResponse:
    query = _joined_query().where(JobMatch.id == job_match_id)
    row = (await db.execute(query)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return _row_to_response(row)
