"""FastAPI router for the application tracker API endpoints."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_application_tracker_status_update_rate_limit
from app.modules.application_tracker import service
from app.modules.application_tracker.schemas import (
    ApplicationStatus,
    TrackedMatchListResponse,
    TrackedMatchResponse,
    UpdateApplicationStatusRequest,
)
from app.observability.application_tracker_metrics import (
    application_tracker_status_updates_total,
)

router = APIRouter(
    prefix="/api/application-tracker", tags=["application-tracker"], route_class=EnvelopeAPIRoute
)


@router.get("/matches", response_model=TrackedMatchListResponse)
async def list_tracked_matches_endpoint(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
    status: ApplicationStatus | None = Query(default=None),
    sort: Literal["newest", "oldest", "score", "recently_updated"] = Query(default="newest"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TrackedMatchListResponse:
    return await service.list_tracked(
        db, current_user.id, status=status, sort=sort, limit=limit, offset=offset
    )


@router.patch(
    "/matches/{match_id}/status",
    response_model=TrackedMatchResponse,
    dependencies=[Depends(enforce_application_tracker_status_update_rate_limit)],
)
async def update_application_status(
    match_id: str,
    payload: UpdateApplicationStatusRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> TrackedMatchResponse:
    result = await service.update_status(
        db, current_user.id, UUID(match_id), payload.application_status
    )
    application_tracker_status_updates_total.inc()
    return result
