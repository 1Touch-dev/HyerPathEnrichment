"""Pydantic request/response shapes for the billing module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserSubscriptionRead(BaseModel):
    """Read-only view of a UserSubscription row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    stripe_customer_id: str
    stripe_subscription_id: str | None
    plan_tier: str
    status: str
    current_period_end: datetime | None
    created_at: datetime
    updated_at: datetime


class CreateCheckoutSessionRequest(BaseModel):
    success_url: str = Field(..., min_length=1, max_length=2048)
    cancel_url: str = Field(..., min_length=1, max_length=2048)


class CheckoutSessionResponse(BaseModel):
    url: str


class CreatePortalSessionRequest(BaseModel):
    return_url: str = Field(..., min_length=1, max_length=2048)


class PortalSessionResponse(BaseModel):
    url: str


class UserSubscriptionResponse(BaseModel):
    """Subscription status for the authenticated candidate."""

    plan_tier: str
    status: str
    current_period_end: datetime | None
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    effective_tier: str
