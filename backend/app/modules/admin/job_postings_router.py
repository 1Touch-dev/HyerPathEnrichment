"""Admin job postings moderation endpoints (Admin Module Phase 2 — moderation
layer). Follows `router.py`'s pattern of inline Pydantic models rather than
`schemas.py` (deliberately untouched by every Batch-1 chunk, see plan)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_admin_moderation_rate_limit
from app.modules.admin.audit import record_admin_action
from app.modules.admin.pagination import decode_cursor, encode_cursor
from app.modules.admin.permissions import require_permission
from app.modules.admin.privileged_operations import (
    begin_idempotent_operation,
    canonical_payload_hash,
    complete_idempotent_operation,
    require_idempotency_key,
)
from app.modules.job_matching.models import JobPosting

router = APIRouter(prefix="/api/admin/job-postings", tags=["admin"], route_class=EnvelopeAPIRoute)


class AdminJobPostingResponse(BaseModel):
    id: UUID
    title: str
    company: str
    location: str | None
    remote: bool
    source: str
    source_url: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    posted_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    is_active: bool
    moderation_status: str
    moderated_by: UUID | None
    moderated_at: datetime | None


class AdminJobPostingListResponse(BaseModel):
    items: list[AdminJobPostingResponse]
    next_cursor: str | None
    has_more: bool


class ModerateJobPostingRequest(BaseModel):
    moderation_status: Literal["active", "hidden", "removed"]
    reason: str | None = Field(default=None, max_length=500)


def _to_response(posting: JobPosting) -> AdminJobPostingResponse:
    return AdminJobPostingResponse(
        id=posting.id,
        title=posting.title,
        company=posting.company,
        location=posting.location,
        remote=posting.remote,
        source=posting.source,
        source_url=posting.source_url,
        salary_min=posting.salary_min,
        salary_max=posting.salary_max,
        salary_currency=posting.salary_currency,
        posted_at=posting.posted_at,
        first_seen_at=posting.first_seen_at,
        last_seen_at=posting.last_seen_at,
        is_active=posting.is_active,
        moderation_status=posting.moderation_status,
        moderated_by=posting.moderated_by,
        moderated_at=posting.moderated_at,
    )


async def _get_posting_or_404(db: AsyncSession, job_posting_id: UUID) -> JobPosting:
    result = await db.execute(select(JobPosting).where(JobPosting.id == job_posting_id))
    posting = result.scalar_one_or_none()
    if posting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job posting not found")
    return posting


@router.get("", response_model=AdminJobPostingListResponse)
async def list_job_postings(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    moderation_status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    _user: User = Depends(require_permission("job_postings", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminJobPostingListResponse:
    # This table has no plain `created_at` — `first_seen_at` is its creation
    # timestamp, so it plays the role `created_at` plays in other admin list
    # endpoints (Decision 4's Stripe-style opaque cursor).
    query = select(JobPosting).order_by(JobPosting.first_seen_at.desc(), JobPosting.id.desc())
    if moderation_status is not None:
        query = query.where(JobPosting.moderation_status == moderation_status)
    if source is not None:
        query = query.where(JobPosting.source == source)
    if is_active is not None:
        query = query.where(JobPosting.is_active == is_active)
    if cursor:
        first_seen_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (JobPosting.first_seen_at < first_seen_at)
            | ((JobPosting.first_seen_at == first_seen_at) & (JobPosting.id < UUID(entity_id)))
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].first_seen_at, rows[-1].id) if has_more and rows else None

    return AdminJobPostingListResponse(
        items=[_to_response(r) for r in rows], next_cursor=next_cursor, has_more=has_more
    )


@router.get("/{job_posting_id}", response_model=AdminJobPostingResponse)
async def get_job_posting(
    job_posting_id: UUID,
    _user: User = Depends(require_permission("job_postings", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminJobPostingResponse:
    posting = await _get_posting_or_404(db, job_posting_id)
    return _to_response(posting)


@router.post(
    "/{job_posting_id}/moderate",
    response_model=AdminJobPostingResponse,
    dependencies=[Depends(enforce_admin_moderation_rate_limit)],
)
async def moderate_job_posting(
    job_posting_id: UUID,
    payload: ModerateJobPostingRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(require_permission("job_postings", "moderate")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminJobPostingResponse:
    """Direct support-escalation action that bypasses the review queue."""
    normalized_key = require_idempotency_key("job_postings.moderate", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=current_user.id,
        operation_id="job_postings.moderate",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash(
            {
                "job_posting_id": job_posting_id,
                "moderation_status": payload.moderation_status,
                "reason": payload.reason,
            }
        ),
    )
    if replay is not None:
        return AdminJobPostingResponse.model_validate(replay.response_body["job_posting"])

    posting = await _get_posting_or_404(db, job_posting_id)

    before = {"moderation_status": posting.moderation_status}
    posting.moderation_status = payload.moderation_status
    posting.moderated_by = current_user.id
    posting.moderated_at = datetime.now(UTC)
    await db.flush()
    after = {"moderation_status": posting.moderation_status, "reason": payload.reason}

    await record_admin_action(
        db,
        actor_user_id=current_user.id,
        action="job_postings.moderate",
        target_type="job_posting",
        target_id=str(job_posting_id),
        before=before,
        after=after,
        ip_address=get_client_ip(request),
    )
    response = _to_response(posting)
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=200,
            response_body={"job_posting": response.model_dump(mode="json")},
        )
    await db.commit()
    await db.refresh(posting)
    return response
