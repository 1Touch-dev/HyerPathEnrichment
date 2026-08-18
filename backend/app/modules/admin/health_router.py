"""System health endpoint (§8.15)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin import health
from app.modules.admin.permissions import require_permission
from app.modules.admin.schemas import SystemHealthResponse

router = APIRouter(
    prefix="/api/admin/system-health", tags=["admin"], route_class=EnvelopeAPIRoute
)


@router.get("", response_model=SystemHealthResponse)
async def get_system_health(
    _user: User = Depends(require_permission("system_health", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> SystemHealthResponse:
    return await health.get_system_health(db)
