"""Admin CRUD endpoints for Brand management. Mirrors
backend/app/modules/admin/roles_router.py's require_permission/EnvelopeAPIRoute
pattern exactly. Brand is presentation-only (docs/adr/0019-tenancy-model.md) —
these endpoints manage brand metadata/config only, never access-control
scoping. No query here (or anywhere else) filters another table by brand_id."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin.permissions import require_permission
from app.modules.brands import repository
from app.modules.brands.schemas import BrandCreate, BrandResponse

router = APIRouter(prefix="/api/admin/brands", tags=["admin"], route_class=EnvelopeAPIRoute)


class BrandUpdateRequest(BaseModel):
    """PATCH body for updating a brand. Deliberately excludes `is_active` —
    brand activation/deactivation is its own audited flow
    (post-tenancy-features/03-org-offboarding-and-deletion.md's deactivation
    router/service), not a plain field edit through this endpoint."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    custom_domain: str | None = None
    chatbot_config: dict[str, Any] | None = None
    landing_page_tier_config: dict[str, Any] | None = None


@router.get("", response_model=list[BrandResponse])
async def list_brands(
    _user: User = Depends(require_permission("brands", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> list[BrandResponse]:
    brands = await repository.list_all_brands(db)
    return [BrandResponse.model_validate(brand) for brand in brands]


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(
    body: BrandCreate,
    _user: User = Depends(require_permission("brands", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> BrandResponse:
    brand = await repository.create_brand(db, **body.model_dump())
    return BrandResponse.model_validate(brand)


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: UUID,
    _user: User = Depends(require_permission("brands", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> BrandResponse:
    brand = await repository.get_brand_by_id(db, brand_id)
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return BrandResponse.model_validate(brand)


@router.patch("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: UUID,
    body: BrandUpdateRequest,
    _user: User = Depends(require_permission("brands", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> BrandResponse:
    fields = body.model_dump(exclude_unset=True)
    brand = await repository.update_brand(db, brand_id, **fields)
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return BrandResponse.model_validate(brand)
