"""Admin CRUD endpoints for Brand management. Mirrors
backend/app/modules/admin/roles_router.py's require_permission/EnvelopeAPIRoute
pattern exactly. Brand is presentation-only (docs/adr/0019-tenancy-model.md) —
these endpoints manage brand metadata/config only, never access-control
scoping. No query here (or anywhere else) filters another table by brand_id."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin.audit import record_admin_action
from app.modules.admin.permissions import require_permission
from app.modules.admin.privileged_operations import (
    begin_idempotent_operation,
    canonical_payload_hash,
    complete_idempotent_operation,
    require_idempotency_key,
)
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
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    user: User = Depends(require_permission("brands", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> BrandResponse:
    normalized_key = require_idempotency_key("brand.create", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=user.id,
        operation_id="brand.create",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash(body.model_dump()),
    )
    if replay is not None:
        return BrandResponse.model_validate(replay.response_body["brand"])

    existing = await repository.get_brand_by_slug(db, body.slug)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already taken")
    try:
        brand = await repository.create_brand(db, **body.model_dump())
        await record_admin_action(
            db,
            actor_user_id=user.id,
            action="brand.create",
            target_type="brand",
            target_id=str(brand.id),
            before=None,
            after=BrandResponse.model_validate(brand).model_dump(mode="json"),
            ip_address=get_client_ip(request),
        )
        response = BrandResponse.model_validate(brand)
        if state is not None:
            await complete_idempotent_operation(
                db,
                state,
                response_status=201,
                response_body={"brand": response.model_dump(mode="json")},
            )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Slug already taken"
        ) from None
    return response


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
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    user: User = Depends(require_permission("brands", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> BrandResponse:
    normalized_key = require_idempotency_key("brand.update", idempotency_key)
    fields = body.model_dump(exclude_unset=True)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=user.id,
        operation_id="brand.update",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash({"brand_id": brand_id, **fields}),
    )
    if replay is not None:
        return BrandResponse.model_validate(replay.response_body["brand"])

    existing_brand = await repository.get_brand_by_id(db, brand_id)
    if existing_brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")

    before = BrandResponse.model_validate(existing_brand).model_dump(mode="json")
    if "slug" in fields:
        existing = await repository.get_brand_by_slug(db, fields["slug"])
        if existing is not None and existing.id != brand_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already taken")
    try:
        brand = await repository.update_brand(db, brand_id, **fields)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Slug already taken"
        ) from None
    try:
        await record_admin_action(
            db,
            actor_user_id=user.id,
            action="brand.update",
            target_type="brand",
            target_id=str(brand_id),
            before=before,
            after=BrandResponse.model_validate(brand).model_dump(mode="json"),
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
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Slug already taken"
        ) from None
    return response
