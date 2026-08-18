"""Job-match analytics endpoint (§8.15). `?refresh=1` wired to
`cached_aggregate`'s `refresh` flag via `analytics.get_job_match_analytics`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin import analytics
from app.modules.admin.permissions import require_permission
from app.modules.admin.schemas import JobMatchAnalyticsResponse

router = APIRouter(
    prefix="/api/admin/analytics", tags=["admin"], route_class=EnvelopeAPIRoute
)


@router.get("/job-matches", response_model=JobMatchAnalyticsResponse)
async def get_job_match_analytics(
    refresh: bool = Query(default=False),
    _user: User = Depends(require_permission("analytics", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> JobMatchAnalyticsResponse:
    return await analytics.get_job_match_analytics(db, refresh=refresh)
