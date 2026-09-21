"""Admin API routes for portfolio profile moderation (Admin Module Phase 2).

Routes are thin — auth/permission check, one query/mutation, return. Request/
response models are defined inline here (matching app/modules/admin/router.py's
pattern), since this module has no dedicated schemas.py of its own."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_admin_moderation_rate_limit
from app.modules.admin.audit import record_admin_action
from app.modules.admin.pagination import decode_cursor, encode_cursor
from app.modules.admin.permissions import require_permission
from app.modules.admin.privileged_operations import (
    begin_idempotent_operation,
    canonical_payload_hash,
    complete_idempotent_operation,
    require_idempotency_key,
)
from app.modules.portfolio.models import PortfolioItem, PortfolioProfile

router = APIRouter(prefix="/api/admin/portfolio", tags=["admin"], route_class=EnvelopeAPIRoute)


class AdminPortfolioProfileResponse(BaseModel):
    profile_id: str
    user_id: str
    slug: str
    display_name: str | None
    headline: str | None
    bio: str | None
    is_published: bool
    admin_hidden: bool
    created_at: datetime
    updated_at: datetime


class AdminPortfolioProfileListResponse(BaseModel):
    items: list[AdminPortfolioProfileResponse]
    next_cursor: str | None
    has_more: bool


class AdminPortfolioItemResponse(BaseModel):
    item_id: str
    item_type: str
    title: str
    description: str | None
    url: str
    image_url: str | None
    display_order: int
    created_at: datetime


class AdminPortfolioProfileDetailResponse(AdminPortfolioProfileResponse):
    items: list[AdminPortfolioItemResponse]


class ModeratePortfolioRequest(BaseModel):
    admin_hidden: bool
    reason: str | None = Field(default=None, max_length=500)


def _profile_to_response(profile: PortfolioProfile) -> AdminPortfolioProfileResponse:
    return AdminPortfolioProfileResponse(
        profile_id=str(profile.id),
        user_id=str(profile.user_id),
        slug=profile.slug,
        display_name=profile.display_name,
        headline=profile.headline,
        bio=profile.bio,
        is_published=profile.is_published,
        admin_hidden=profile.admin_hidden,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _item_to_response(item: PortfolioItem) -> AdminPortfolioItemResponse:
    return AdminPortfolioItemResponse(
        item_id=str(item.id),
        item_type=item.item_type,
        title=item.title,
        description=item.description,
        url=item.url,
        image_url=item.image_url,
        display_order=item.display_order,
        created_at=item.created_at,
    )


@router.get("", response_model=AdminPortfolioProfileListResponse)
async def list_portfolio_profiles(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    is_published: bool | None = Query(default=None),
    admin_hidden: bool | None = Query(default=None),
    _user: User = Depends(require_permission("portfolio", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminPortfolioProfileListResponse:
    query = select(PortfolioProfile).order_by(
        PortfolioProfile.created_at.desc(), PortfolioProfile.id.desc()
    )
    if is_published is not None:
        query = query.where(PortfolioProfile.is_published == is_published)
    if admin_hidden is not None:
        query = query.where(PortfolioProfile.admin_hidden == admin_hidden)
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (PortfolioProfile.created_at < created_at)
            | (
                (PortfolioProfile.created_at == created_at)
                & (PortfolioProfile.id < UUID(entity_id))
            )
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None

    return AdminPortfolioProfileListResponse(
        items=[_profile_to_response(p) for p in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{profile_id}", response_model=AdminPortfolioProfileDetailResponse)
async def get_portfolio_profile(
    profile_id: UUID,
    _user: User = Depends(require_permission("portfolio", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminPortfolioProfileDetailResponse:
    profile = (
        await db.execute(select(PortfolioProfile).where(PortfolioProfile.id == profile_id))
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio profile not found"
        )

    items = list(
        (
            await db.execute(
                select(PortfolioItem)
                .where(PortfolioItem.profile_id == profile.id)
                .order_by(PortfolioItem.display_order)
            )
        )
        .scalars()
        .all()
    )

    base = _profile_to_response(profile)
    return AdminPortfolioProfileDetailResponse(
        **base.model_dump(),
        items=[_item_to_response(i) for i in items],
    )


@router.post(
    "/{profile_id}/moderate",
    response_model=AdminPortfolioProfileResponse,
    dependencies=[Depends(enforce_admin_moderation_rate_limit)],
)
async def moderate_portfolio_profile(
    profile_id: UUID,
    payload: ModeratePortfolioRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(require_permission("portfolio", "moderate")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminPortfolioProfileResponse:
    normalized_key = require_idempotency_key("portfolio.moderate", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=current_user.id,
        operation_id="portfolio.moderate",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash(
            {
                "profile_id": profile_id,
                "admin_hidden": payload.admin_hidden,
                "reason": payload.reason,
            }
        ),
    )
    if replay is not None:
        return AdminPortfolioProfileResponse.model_validate(replay.response_body["profile"])

    profile = (
        await db.execute(select(PortfolioProfile).where(PortfolioProfile.id == profile_id))
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio profile not found"
        )

    before = {"admin_hidden": profile.admin_hidden}
    profile.admin_hidden = payload.admin_hidden
    await db.flush()
    after = {"admin_hidden": profile.admin_hidden, "reason": payload.reason}

    await record_admin_action(
        db,
        actor_user_id=current_user.id,
        action="portfolio.moderate",
        target_type="portfolio_profile",
        target_id=str(profile_id),
        before=before,
        after=after,
        ip_address=get_client_ip(request),
    )
    response = _profile_to_response(profile)
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=200,
            response_body={"profile": response.model_dump(mode="json")},
        )
    await db.commit()
    await db.refresh(profile)
    return response
