"""HTTP schemas for the portfolio module. Slug validation lives here ONLY (RULE.md: no duplicate validation)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PORTFOLIO_SLUG_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$"
)  # RFC 1035 label charset (Decision 4)


PortfolioItemType = Literal["github", "live_demo", "case_study", "other"]


class PortfolioItemRequest(BaseModel):
    item_type: PortfolioItemType
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    url: str = Field(..., min_length=1, max_length=2048)
    image_url: str | None = Field(default=None, max_length=2048)
    display_order: int = 0


class PortfolioItemResponse(BaseModel):
    """Not inheriting PortfolioItemRequest: item_type is a plain str here (DB column is Mapped[str],
    validated on write, not on read) — same convention as job_swipe/schemas.py's SwipeActionResponse,
    which independently redeclares `direction: str` instead of inheriting SwipeActionRequest's Literal."""

    item_id: str
    item_type: str
    title: str
    description: str | None
    url: str
    image_url: str | None = Field(default=None, max_length=2048)
    display_order: int
    created_at: datetime


class PortfolioProfileRequest(BaseModel):
    slug: str = Field(..., min_length=3, max_length=63)
    display_name: str | None = Field(default=None, max_length=255)
    headline: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=5000)
    is_published: bool = False

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        v = v.lower().strip()
        if not PORTFOLIO_SLUG_PATTERN.match(v):
            raise ValueError(
                "Slug must be 3-63 lowercase alphanumeric characters or hyphens, "
                "not starting/ending with a hyphen (subdomain-compatible charset, see Decision 4)"
            )
        return v


class PortfolioProfileResponse(PortfolioProfileRequest):
    profile_id: str
    user_id: str
    public_url: str
    items: list[PortfolioItemResponse]
    created_at: datetime
    updated_at: datetime


class PublicPortfolioResponse(BaseModel):
    """What an unauthenticated visitor to /p/{slug} sees — no user_id, no internal IDs beyond item_id."""

    slug: str
    display_name: str | None
    headline: str | None
    bio: str | None
    items: list[PortfolioItemResponse]
