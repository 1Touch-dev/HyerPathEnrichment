"""FastAPI router for manual job entry API endpoints (Module 4, Module F).

v1 is create-only (§14 non-goal: "Editing or deleting a manual job entry") —
this router deliberately exposes only POST /api/manual-jobs. No GET/PATCH/DELETE.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_manual_job_entry_create_rate_limit
from app.modules.manual_jobs import service
from app.modules.manual_jobs.schemas import CreateManualJobEntryRequest, ManualJobEntryResponse

router = APIRouter(prefix="/api/manual-jobs", tags=["manual-jobs"], route_class=EnvelopeAPIRoute)


@router.post(
    "",
    response_model=ManualJobEntryResponse,
    dependencies=[Depends(enforce_manual_job_entry_create_rate_limit)],
)
async def create_manual_job_entry(
    request: CreateManualJobEntryRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> ManualJobEntryResponse:
    return await service.create_manual_entry(db, current_user.id, request)
