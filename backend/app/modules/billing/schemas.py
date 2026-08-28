"""Pydantic read-shapes for the billing module. Kept minimal by design -- no
router exists yet to consume a broader request/response surface (see
task-orchestration/post-tenancy-features/01-billing-stripe-integration.md's
"Files to create" list: router.py/webhook_router.py are deferred). This file
only backs repository.py/future callers' return types today."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
