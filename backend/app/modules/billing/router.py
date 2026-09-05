"""Authenticated billing routes — checkout, portal, subscription status."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.billing import service
from app.modules.billing.schemas import (
    CheckoutSessionResponse,
    CreateCheckoutSessionRequest,
    CreatePortalSessionRequest,
    PortalSessionResponse,
    UserSubscriptionResponse,
)

router = APIRouter(prefix="/api/billing", tags=["billing"], route_class=EnvelopeAPIRoute)


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    body: CreateCheckoutSessionRequest,
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> CheckoutSessionResponse:
    return await service.create_checkout_session_for_user(
        db,
        user,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )


@router.post("/portal-session", response_model=PortalSessionResponse)
async def create_portal_session(
    body: CreatePortalSessionRequest,
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> PortalSessionResponse:
    return await service.create_portal_session_for_user(
        db,
        user,
        return_url=body.return_url,
    )


@router.get("/subscription", response_model=UserSubscriptionResponse)
async def get_subscription(
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> UserSubscriptionResponse:
    return await service.get_subscription_status(db, user.id)
