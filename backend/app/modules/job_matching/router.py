"""FastAPI router for job matching API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, StreamingResponse

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import (
    enforce_job_matching_apply_rate_limit,
    enforce_job_matching_scan_rate_limit,
)
from app.modules.job_matching import events, push, repository
from app.modules.job_matching.schemas import (
    JobMatchFeedbackRequest,
    JobMatchListResponse,
    JobPreferencesRequest,
    JobPreferencesResponse,
    MarkAppliedRequest,
    PushSubscriptionRequest,
    PushUnsubscribeRequest,
    ScanTriggerResponse,
)
from app.modules.job_matching.service import JobMatchingService

router = APIRouter(prefix="/api/job-matching", tags=["job-matching"], route_class=EnvelopeAPIRoute)


@router.get("/preferences", response_model=JobPreferencesResponse)
async def get_preferences(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> JobPreferencesResponse:
    service = JobMatchingService(db)
    return await service.get_preferences(current_user.id)


@router.put("/preferences", response_model=JobPreferencesResponse)
async def upsert_preferences(
    payload: JobPreferencesRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> JobPreferencesResponse:
    service = JobMatchingService(db)
    return await service.upsert_preferences(current_user.id, payload)


@router.get("/matches", response_model=JobMatchListResponse)
async def list_matches(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JobMatchListResponse:
    service = JobMatchingService(db)
    return await service.list_matches(current_user.id, limit, offset)


@router.post("/matches/{match_id}/view", status_code=status.HTTP_204_NO_CONTENT)
async def mark_match_viewed(
    match_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> None:
    service = JobMatchingService(db)
    await service.mark_viewed(match_id, current_user.id)


@router.post("/matches/{match_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def submit_match_feedback(
    match_id: str,
    payload: JobMatchFeedbackRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    service = JobMatchingService(db)
    await service.set_feedback(match_id, current_user.id, payload.feedback)


@router.get(
    "/matches/{match_id}/apply-redirect",
    dependencies=[Depends(enforce_job_matching_apply_rate_limit)],
)
async def apply_redirect(
    match_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> RedirectResponse:
    """Records the click server-side, then 302s to the posting's own source_url.

    Open-redirect guard (hard requirement): the ONLY URL ever redirected to is
    `source_url` already stored on the JobPosting row joined through this exact
    match_id + current_user.id pair — there is no query parameter or request body
    input that influences the redirect target. A match_id belonging to a different
    user 404s (never leaks another candidate's saved posting), and a posting with
    no source_url (should not normally happen — JobSpy/JSearch rows always populate
    it, but defensive) 404s rather than redirecting to a blank/relative URL.
    """
    service = JobMatchingService(db)
    target_url = await service.record_apply_click_and_get_redirect_url(match_id, current_user.id)
    return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)


@router.post(
    "/matches/{match_id}/mark-applied",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(enforce_job_matching_apply_rate_limit)],
)
async def mark_applied(
    match_id: str,
    payload: MarkAppliedRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    service = JobMatchingService(db)
    await service.set_applied(match_id, current_user.id, payload.applied)


@router.post(
    "/scan",
    response_model=ScanTriggerResponse,
    dependencies=[Depends(enforce_job_matching_scan_rate_limit)],
)
async def trigger_scan(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> ScanTriggerResponse:
    service = JobMatchingService(db)
    return await service.trigger_scan(current_user.id)


@router.get("/events")
async def stream_unread_match_events(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> StreamingResponse:
    """SSE stream of the caller's live unread-match count. Re-checks Postgres for the
    current count on every (re)connect, then pushes subsequent updates as new matches
    are scored. Clients without SSE support should keep polling `GET /matches`."""
    initial_count = await repository.count_unread_matches(db, current_user.id)
    return StreamingResponse(
        events.stream_unread_match_events(str(current_user.id), initial_count),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/push-subscription", status_code=status.HTTP_204_NO_CONTENT)
async def create_push_subscription(
    payload: PushSubscriptionRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await push.subscribe(db, current_user.id, payload.endpoint, payload.p256dh, payload.auth)


@router.delete("/push-subscription", status_code=status.HTTP_204_NO_CONTENT)
async def delete_push_subscription(
    payload: PushUnsubscribeRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await push.unsubscribe(db, current_user.id, payload.endpoint)
