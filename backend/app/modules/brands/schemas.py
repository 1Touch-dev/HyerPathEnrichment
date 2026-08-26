"""HTTP schemas for the brands module. Presentation-only fields — see
docs/adr/0019-tenancy-model.md; no field here is ever used as an access-scoping value."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BrandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    custom_domain: str | None = None
    chatbot_config: dict[str, Any] | None = None
    landing_page_tier_config: dict[str, Any] | None = None


class BrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    custom_domain: str | None
    chatbot_config: dict[str, Any] | None
    landing_page_tier_config: dict[str, Any] | None
    is_active: bool
    created_at: datetime
