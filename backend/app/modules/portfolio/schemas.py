"""HTTP schemas for the portfolio module. Slug validation lives here ONLY (RULE.md: no duplicate validation)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.portfolio.content import (
    PortfolioContent,
    PortfolioRevision,
    PortfolioTemplateId,
    PortfolioThemeConfig,
    default_section_order,
    default_section_visibility,
)

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
    """Upsert body. Legacy fields remain; studio fields are additive.

    - Saving without `publish=True` updates the draft revision only.
    - `is_published` alone still toggles visibility of the *published* revision
      (backward compatible with the pre-studio editor).
    - `publish=True` copies the draft revision into the published snapshot and
      sets `is_published=True`.
    """

    slug: str = Field(..., min_length=3, max_length=63)
    display_name: str | None = Field(default=None, max_length=255)
    headline: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=5000)
    is_published: bool = False
    # Studio fields (optional — omitted means "leave draft studio fields alone"
    # except when creating a new profile, in which case defaults apply).
    template_id: PortfolioTemplateId | None = None
    theme: PortfolioThemeConfig | None = None
    content: PortfolioContent | None = None
    section_visibility: dict[str, bool] | None = None
    section_order: list[str] | None = None
    publish: bool = False

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


class PortfolioProfileResponse(BaseModel):
    profile_id: str
    user_id: str
    slug: str
    display_name: str | None
    headline: str | None
    bio: str | None
    is_published: bool
    public_url: str
    items: list[PortfolioItemResponse]
    created_at: datetime
    updated_at: datetime
    # Studio draft state (what the editor edits / previews)
    template_id: PortfolioTemplateId = "minimal_professional"
    theme: PortfolioThemeConfig = Field(default_factory=PortfolioThemeConfig)
    content: PortfolioContent = Field(default_factory=PortfolioContent)
    section_visibility: dict[str, bool] = Field(default_factory=default_section_visibility)
    section_order: list[str] = Field(default_factory=default_section_order)
    # True when draft differs from the last published snapshot
    has_unpublished_changes: bool = False
    draft_revision: PortfolioRevision = Field(default_factory=PortfolioRevision)
    published_revision: PortfolioRevision | None = None


class PublicPortfolioResponse(BaseModel):
    """What an unauthenticated visitor to /p/{slug} sees — published revision only."""

    slug: str
    display_name: str | None
    headline: str | None
    bio: str | None
    items: list[PortfolioItemResponse]
    template_id: PortfolioTemplateId = "minimal_professional"
    theme: PortfolioThemeConfig = Field(default_factory=PortfolioThemeConfig)
    content: PortfolioContent = Field(default_factory=PortfolioContent)
    section_visibility: dict[str, bool] = Field(default_factory=default_section_visibility)
    section_order: list[str] = Field(default_factory=default_section_order)


class PublishPortfolioResponse(BaseModel):
    profile: PortfolioProfileResponse
    published: bool = True
