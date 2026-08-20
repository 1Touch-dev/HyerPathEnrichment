"""FastAPI router for interview scheduling API endpoints (Module 4, Module D).

Registered in app/main.py alongside Track E's jd_practice_router as part of
the Phase 3.5 reconciliation step.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.core.config import get_settings
from app.database.session import get_db_session
from app.modules.interview_scheduling import repository
from app.modules.interview_scheduling.ics_builder import build_ics
from app.modules.interview_scheduling.schemas import (
    InterviewScheduleResponse,
    ScheduleInterviewRequest,
)
from app.modules.interview_scheduling.service import _send_scheduled_notification, _to_response
from app.modules.job_matching import repository as job_matching_repository
from app.modules.job_matching import service as job_matching_service
from app.observability.interview_scheduling_metrics import interview_schedules_created_total
from app.workers import queue

router = APIRouter(
    prefix="/api/interviews", tags=["interview-scheduling"], route_class=EnvelopeAPIRoute
)


@router.post("/matches/{match_id}/schedule", response_model=InterviewScheduleResponse)
async def schedule_interview(
    match_id: str,
    payload: ScheduleInterviewRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> InterviewScheduleResponse:
    """Creates/updates the InterviewSchedule row, advances the JobMatch's
    application_status to "interview" (Module C integration — same forward-fill-only
    rule as Module B's mark-applied: only auto-advance if current status isn't
    already past "interview" e.g. don't downgrade "offer" back to "interview"),
    and enqueues both the confirmation notification (email+push, §8.5) and the
    reminder job (§8.6).
    """
    if payload.scheduled_at <= datetime.now(UTC):
        raise HTTPException(status_code=422, detail="scheduled_at must be in the future")

    owned = await job_matching_repository.get_owned_match(db, UUID(match_id), current_user.id)
    if owned is None:
        raise HTTPException(status_code=404, detail="Match not found")
    match, posting = owned

    schedule = await repository.upsert_schedule(
        db,
        job_match_id=match.id,
        user_id=current_user.id,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        notes=payload.notes,
    )

    await job_matching_service.advance_application_status_if_earlier(db, match, target="interview")

    await _send_scheduled_notification(db, current_user, match, posting, schedule)

    send_at = payload.scheduled_at - timedelta(hours=get_settings().interview_reminder_hours_before)
    queue.enqueue_interview_reminder(str(schedule.id), send_at)

    interview_schedules_created_total.inc()

    return _to_response(schedule)


@router.get("/matches/{match_id}/schedule", response_model=InterviewScheduleResponse | None)
async def get_interview_schedule(
    match_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> InterviewScheduleResponse | None:
    schedule = await repository.get_schedule_for_match(db, UUID(match_id), current_user.id)
    return _to_response(schedule) if schedule else None


@router.delete("/matches/{match_id}/schedule", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_interview(
    match_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Deletes the InterviewSchedule row. Does NOT auto-revert application_status —
    a candidate who cancels a scheduling row after actually attending (rescheduling
    flow) shouldn't have their status silently reset; status stays a manual field
    (Module C's core design tenet), this endpoint only removes the calendar artifact.
    Also cancels the pending reminder job via RQ's cancel_job (no-op, logged at
    warning level, if the job already fired or already ran — same idempotent-cancel
    pattern as job_matching's existing scan-cancellation path).
    """
    schedule = await repository.get_schedule_for_match(db, UUID(match_id), current_user.id)
    if schedule is None:
        return
    queue.cancel_interview_reminder(str(schedule.id))
    await repository.delete_schedule(db, schedule.id)


@router.get("/matches/{match_id}/schedule.ics")
async def download_ics(
    match_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Returns the .ics file with Content-Type: text/calendar; charset=utf-8 and
    Content-Disposition: attachment so the browser downloads/opens-in-calendar-app
    rather than rendering the raw ICS text.
    """
    owned = await job_matching_repository.get_owned_match(db, UUID(match_id), current_user.id)
    if owned is None:
        raise HTTPException(status_code=404, detail="Match not found")
    match, posting = owned
    schedule = await repository.get_schedule_for_match(db, match.id, current_user.id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="No interview scheduled for this match")

    title = posting.title if posting else "your role"
    company = posting.company if posting else "the company"
    settings = get_settings()
    # settings.interview_ics_organizer_email has no safe default of its own (§4) —
    # falls back to sendgrid_from_email if left blank, per that field's own docstring.
    organizer_email = settings.interview_ics_organizer_email or settings.sendgrid_from_email
    ics_body = build_ics(
        uid=f"interview-{schedule.id}@hyerenrichment",
        summary=f"Interview: {title} at {company}",
        description=schedule.notes or f"Interview for {title} at {company}",
        location=None,
        start=schedule.scheduled_at,
        duration_minutes=schedule.duration_minutes,
        organizer_email=organizer_email,
    )
    return Response(
        content=ics_body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="interview-{schedule.id}.ics"'},
    )
