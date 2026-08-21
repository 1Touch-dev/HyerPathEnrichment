"""Admin moderation endpoints for interview schedules (Admin Module — Module 4
admin visibility/moderation surface, migration 046). An admin-initiated
"cancel" is a SOFT cancel (`admin_cancelled_at`/`admin_cancelled_by`),
distinct from the candidate-facing hard-delete `cancel_interview` route in
`app/modules/interview_scheduling/router.py` — the row is preserved for
audit/history rather than removed."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
from app.modules.interview_scheduling.models import InterviewSchedule
from app.workers import queue

router = APIRouter(
    prefix="/api/admin/interview-schedules", tags=["admin"], route_class=EnvelopeAPIRoute
)


class AdminInterviewScheduleResponse(BaseModel):
    id: UUID
    job_match_id: UUID
    user_id: UUID
    scheduled_at: datetime
    duration_minutes: int
    notes: str | None
    admin_cancelled_at: datetime | None
    admin_cancelled_by: UUID | None
    created_at: datetime
    updated_at: datetime | None


class AdminInterviewScheduleListResponse(BaseModel):
    items: list[AdminInterviewScheduleResponse]
    next_cursor: str | None
    has_more: bool


class ModerateInterviewScheduleRequest(BaseModel):
    action: Literal["cancel", "restore"]
    reason: str | None = Field(default=None, max_length=500)


def _to_response(schedule: InterviewSchedule) -> AdminInterviewScheduleResponse:
    return AdminInterviewScheduleResponse(
        id=schedule.id,
        job_match_id=schedule.job_match_id,
        user_id=schedule.user_id,
        scheduled_at=schedule.scheduled_at,
        duration_minutes=schedule.duration_minutes,
        notes=schedule.notes,
        admin_cancelled_at=schedule.admin_cancelled_at,
        admin_cancelled_by=schedule.admin_cancelled_by,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


async def _get_schedule_or_404(db: AsyncSession, schedule_id: UUID) -> InterviewSchedule:
    result = await db.execute(select(InterviewSchedule).where(InterviewSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview schedule not found")
    return schedule


@router.get("", response_model=AdminInterviewScheduleListResponse)
async def list_interview_schedules(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    admin_cancelled: bool | None = Query(default=None),
    _user: User = Depends(require_permission("interview_schedules", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminInterviewScheduleListResponse:
    query = select(InterviewSchedule).order_by(
        InterviewSchedule.created_at.desc(), InterviewSchedule.id.desc()
    )
    if admin_cancelled is not None:
        if admin_cancelled:
            query = query.where(InterviewSchedule.admin_cancelled_at.is_not(None))
        else:
            query = query.where(InterviewSchedule.admin_cancelled_at.is_(None))
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (InterviewSchedule.created_at < created_at)
            | (
                (InterviewSchedule.created_at == created_at)
                & (InterviewSchedule.id < UUID(entity_id))
            )
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None

    return AdminInterviewScheduleListResponse(
        items=[_to_response(r) for r in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{schedule_id}", response_model=AdminInterviewScheduleResponse)
async def get_interview_schedule(
    schedule_id: UUID,
    _user: User = Depends(require_permission("interview_schedules", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminInterviewScheduleResponse:
    schedule = await _get_schedule_or_404(db, schedule_id)
    return _to_response(schedule)


@router.post(
    "/{schedule_id}/moderate",
    response_model=AdminInterviewScheduleResponse,
    dependencies=[Depends(enforce_admin_moderation_rate_limit)],
)
async def moderate_interview_schedule(
    schedule_id: UUID,
    payload: ModerateInterviewScheduleRequest,
    request: Request,
    current_user: User = Depends(require_permission("interview_schedules", "moderate")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminInterviewScheduleResponse:
    schedule = await _get_schedule_or_404(db, schedule_id)

    before = {
        "admin_cancelled_at": schedule.admin_cancelled_at.isoformat()
        if schedule.admin_cancelled_at
        else None,
    }
    if payload.action == "cancel":
        schedule.admin_cancelled_at = datetime.now(UTC)
        schedule.admin_cancelled_by = current_user.id
        queue.cancel_interview_reminder(str(schedule.id))
    else:
        schedule.admin_cancelled_at = None
        schedule.admin_cancelled_by = None
    await db.flush()
    after = {
        "admin_cancelled_at": schedule.admin_cancelled_at.isoformat()
        if schedule.admin_cancelled_at
        else None,
        "reason": payload.reason,
    }

    await record_admin_action(
        db,
        actor_user_id=current_user.id,
        action="interview_schedules.moderate",
        target_type="interview_schedule",
        target_id=str(schedule_id),
        before=before,
        after=after,
        ip_address=get_client_ip(request),
    )
    await db.commit()
    await db.refresh(schedule)
    return _to_response(schedule)
