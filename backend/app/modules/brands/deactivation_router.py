"""Admin API routes for turning a brand's public presentation on/off.

Only two routes in this chunk's scope — deactivate and reactivate. See
task-orchestration/post-tenancy-features/03-org-offboarding-and-deletion.md:
there is no third "hard-delete" route here, and neither route touches any
candidate, recruiter, job-match, outreach, or document row. Gated behind
`("brands", "delete")` — reusing the pre-pivot org-deletion permission name
for "can retire a brand" per that doc's "Files to edit" note, even though the
mechanics shrank to a reversible flag flip.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin.permissions import require_permission
from app.modules.brands import deactivation_service
from app.modules.brands.schemas import BrandResponse

router = APIRouter(
    prefix="/api/admin/brands", tags=["admin", "brands"], route_class=EnvelopeAPIRoute
)


class DeactivateBrandRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


@router.post("/{brand_id}/deactivate", response_model=BrandResponse)
async def deactivate_brand_route(
    brand_id: UUID,
    body: DeactivateBrandRequest,
    request: Request,
    user: User = Depends(require_permission("brands", "delete")),
    db: AsyncSession = Depends(get_db_session),
) -> BrandResponse:
    brand = await deactivation_service.deactivate_brand(
        db,
        brand_id=brand_id,
        actor_id=user.id,
        reason=body.reason,
        ip_address=get_client_ip(request),
    )
    return BrandResponse.model_validate(brand)


@router.post("/{brand_id}/reactivate", response_model=BrandResponse)
async def reactivate_brand_route(
    brand_id: UUID,
    request: Request,
    user: User = Depends(require_permission("brands", "delete")),
    db: AsyncSession = Depends(get_db_session),
) -> BrandResponse:
    brand = await deactivation_service.reactivate_brand(
        db,
        brand_id=brand_id,
        actor_id=user.id,
        ip_address=get_client_ip(request),
    )
    return BrandResponse.model_validate(brand)
