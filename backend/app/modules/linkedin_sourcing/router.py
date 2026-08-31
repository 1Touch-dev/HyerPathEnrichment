"""FastAPI router for LinkedIn sourcing leads (manual data-entry only — see
12-linkedin-sourcing-intern-multilogin.md). Create/list/review require
``linkedin_sourcing:write``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin.permissions import require_permission
from app.modules.linkedin_sourcing import service
from app.modules.linkedin_sourcing.schemas import (
    CreateSourcedLeadRequest,
    ReviewSourcedLeadRequest,
    SourcedLeadResponse,
)

router = APIRouter(
    prefix="/api/linkedin-sourcing", tags=["linkedin-sourcing"], route_class=EnvelopeAPIRoute
)


@router.post("/leads", response_model=SourcedLeadResponse)
async def create_lead(
    body: CreateSourcedLeadRequest,
    current_user: User = Depends(require_permission("linkedin_sourcing", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> SourcedLeadResponse:
    return await service.create_lead(db, sourced_by=current_user.id, body=body)


@router.get("/leads", response_model=list[SourcedLeadResponse])
async def list_leads(
    current_user: User = Depends(require_permission("linkedin_sourcing", "write")),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> list[SourcedLeadResponse]:
    return await service.list_leads(db, status=status)


@router.post("/leads/{lead_id}/review", response_model=SourcedLeadResponse)
async def review_lead(
    lead_id: UUID,
    body: ReviewSourcedLeadRequest,
    current_user: User = Depends(require_permission("linkedin_sourcing", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> SourcedLeadResponse:
    return await service.review_lead(db, lead_id=lead_id, reviewer_id=current_user.id, body=body)
