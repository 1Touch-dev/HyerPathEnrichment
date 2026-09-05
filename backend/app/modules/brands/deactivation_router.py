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

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin.permissions import require_permission
from app.modules.admin.privileged_operations import (
    begin_idempotent_operation,
    canonical_payload_hash,
    complete_idempotent_operation,
    require_idempotency_key,
)
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
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    user: User = Depends(require_permission("brands", "delete")),
    db: AsyncSession = Depends(get_db_session),
) -> BrandResponse:
    normalized_key = require_idempotency_key("brand.deactivate", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=user.id,
        operation_id="brand.deactivate",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash({"brand_id": brand_id, "reason": body.reason}),
    )
    if replay is not None:
        return BrandResponse.model_validate(replay.response_body["brand"])

    brand = await deactivation_service.stage_deactivate_brand(
        db,
        brand_id=brand_id,
        actor_id=user.id,
        reason=body.reason,
        ip_address=get_client_ip(request),
    )
    response = BrandResponse.model_validate(brand)
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=200,
            response_body={"brand": response.model_dump(mode="json")},
        )
        await db.commit()
    return response


@router.post("/{brand_id}/reactivate", response_model=BrandResponse)
async def reactivate_brand_route(
    brand_id: UUID,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    user: User = Depends(require_permission("brands", "delete")),
    db: AsyncSession = Depends(get_db_session),
) -> BrandResponse:
    normalized_key = require_idempotency_key("brand.reactivate", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=user.id,
        operation_id="brand.reactivate",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash({"brand_id": brand_id}),
    )
    if replay is not None:
        return BrandResponse.model_validate(replay.response_body["brand"])

    brand = await deactivation_service.stage_reactivate_brand(
        db,
        brand_id=brand_id,
        actor_id=user.id,
        ip_address=get_client_ip(request),
    )
    response = BrandResponse.model_validate(brand)
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=200,
            response_body={"brand": response.model_dump(mode="json")},
        )
        await db.commit()
    return response
