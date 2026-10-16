"""Portfolio Studio content model — template-independent structured data.

Draft and published revisions share this shape. Templates only consume the
validated content; switching templates never mutates these fields.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

PortfolioTemplateId = Literal[
    "minimal_professional",
    "creative_showcase",
    "developer_dark",
    "executive_elegant",
    "personal_story",
]

PORTFOLIO_TEMPLATE_IDS: tuple[PortfolioTemplateId, ...] = (
    "minimal_professional",
    "creative_showcase",
    "developer_dark",
    "executive_elegant",
    "personal_story",
)

DEFAULT_TEMPLATE_ID: PortfolioTemplateId = "minimal_professional"

SECTION_KEYS = (
    "about",
    "projects",
    "experience",
    "education",
    "skills",
    "certifications",
    "social",
    "contact",
)

PaletteId = Literal["neutral", "vibrant", "ocean", "forest", "slate"]
FontPairingId = Literal["sans", "serif", "mono", "editorial"]
SocialPlatform = Literal[
    "github",
    "linkedin",
    "behance",
    "dribbble",
    "twitter",
    "website",
    "other",
]


def _new_id() -> str:
    return str(uuid4())


class PortfolioThemeConfig(BaseModel):
    palette: PaletteId = "neutral"
    accent: str | None = Field(default=None, max_length=32)
    font_pairing: FontPairingId = "sans"

    @field_validator("accent")
    @classmethod
    def _validate_accent(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        v = value.strip()
        if not v.startswith("#") or len(v) not in (4, 7):
            raise ValueError("Accent must be a hex color like #0ea5e9")
        return v


class PortfolioProject(BaseModel):
    id: str = Field(default_factory=_new_id)
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    image_url: str | None = Field(default=None, max_length=2048)
    tech_stack: list[str] = Field(default_factory=list, max_length=30)
    demo_url: str | None = Field(default=None, max_length=2048)
    repo_url: str | None = Field(default=None, max_length=2048)
    display_order: int = 0

    @field_validator("tech_stack")
    @classmethod
    def _trim_stack(cls, value: list[str]) -> list[str]:
        cleaned = [t.strip()[:64] for t in value if t and t.strip()]
        return cleaned[:30]


class PortfolioExperience(BaseModel):
    id: str = Field(default_factory=_new_id)
    company: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    start_date: str | None = Field(default=None, max_length=32)
    end_date: str | None = Field(default=None, max_length=32)
    is_current: bool = False
    description: str | None = Field(default=None, max_length=4000)
    achievements: list[str] = Field(default_factory=list, max_length=20)
    display_order: int = 0


class PortfolioEducation(BaseModel):
    id: str = Field(default_factory=_new_id)
    institution: str = Field(..., min_length=1, max_length=255)
    degree: str | None = Field(default=None, max_length=255)
    field_of_study: str | None = Field(default=None, max_length=255)
    start_year: str | None = Field(default=None, max_length=16)
    end_year: str | None = Field(default=None, max_length=16)
    description: str | None = Field(default=None, max_length=2000)
    activities: list[str] = Field(default_factory=list, max_length=30)
    display_order: int = 0

    @field_validator("activities")
    @classmethod
    def _trim_activities(cls, value: list[str]) -> list[str]:
        cleaned = [a.strip()[:255] for a in value if a and a.strip()]
        return cleaned[:30]


class PortfolioSkill(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str = Field(..., min_length=1, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    level: str | None = Field(default=None, max_length=64)
    display_order: int = 0


class PortfolioCertification(BaseModel):
    id: str = Field(default_factory=_new_id)
    title: str = Field(..., min_length=1, max_length=255)
    issuer: str | None = Field(default=None, max_length=255)
    year: str | None = Field(default=None, max_length=16)
    credential_url: str | None = Field(default=None, max_length=2048)
    display_order: int = 0


class PortfolioSocialLink(BaseModel):
    id: str = Field(default_factory=_new_id)
    platform: SocialPlatform = "other"
    label: str | None = Field(default=None, max_length=120)
    url: str = Field(..., min_length=1, max_length=2048)
    display_order: int = 0


class PortfolioContent(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    professional_role: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = Field(default=None, max_length=5000)
    about: str | None = Field(default=None, max_length=8000)
    profile_image_url: str | None = Field(default=None, max_length=2048)
    cover_image_url: str | None = Field(default=None, max_length=2048)
    email: str | None = Field(default=None, max_length=320)
    resume_url: str | None = Field(default=None, max_length=2048)
    projects: list[PortfolioProject] = Field(default_factory=list, max_length=50)
    experience: list[PortfolioExperience] = Field(default_factory=list, max_length=40)
    education: list[PortfolioEducation] = Field(default_factory=list, max_length=20)
    skills: list[PortfolioSkill] = Field(default_factory=list, max_length=80)
    certifications: list[PortfolioCertification] = Field(default_factory=list, max_length=40)
    social_links: list[PortfolioSocialLink] = Field(default_factory=list, max_length=20)


def default_section_visibility() -> dict[str, bool]:
    return {key: True for key in SECTION_KEYS}


def default_section_order() -> list[str]:
    return list(SECTION_KEYS)


class PortfolioRevision(BaseModel):
    """One complete studio snapshot (draft or published)."""

    template_id: PortfolioTemplateId = DEFAULT_TEMPLATE_ID
    theme: PortfolioThemeConfig = Field(default_factory=PortfolioThemeConfig)
    content: PortfolioContent = Field(default_factory=PortfolioContent)
    section_visibility: dict[str, bool] = Field(default_factory=default_section_visibility)
    section_order: list[str] = Field(default_factory=default_section_order)

    @field_validator("section_order")
    @classmethod
    def _validate_order(cls, value: list[str]) -> list[str]:
        known = set(SECTION_KEYS)
        cleaned = [k for k in value if k in known]
        for key in SECTION_KEYS:
            if key not in cleaned:
                cleaned.append(key)
        return cleaned

    @field_validator("section_visibility")
    @classmethod
    def _validate_visibility(cls, value: dict[str, bool]) -> dict[str, bool]:
        merged = default_section_visibility()
        for key, flag in value.items():
            if key in merged:
                merged[key] = bool(flag)
        return merged


def empty_revision() -> PortfolioRevision:
    return PortfolioRevision()


def revision_from_dict(raw: dict[str, Any] | None) -> PortfolioRevision:
    if not raw:
        return empty_revision()
    return PortfolioRevision.model_validate(raw)


def revision_to_dict(revision: PortfolioRevision) -> dict[str, Any]:
    return revision.model_dump(mode="json")


def hydrate_revision_from_legacy(
    *,
    display_name: str | None,
    headline: str | None,
    bio: str | None,
    items: list[dict[str, Any]] | None = None,
) -> PortfolioRevision:
    """Build a studio revision from pre-studio profile columns + items."""
    projects: list[PortfolioProject] = []
    social: list[PortfolioSocialLink] = []
    for idx, item in enumerate(items or []):
        item_type = str(item.get("item_type") or "other")
        title = str(item.get("title") or "Link")
        url = str(item.get("url") or "")
        description = item.get("description")
        image_url = item.get("image_url")
        order = int(item.get("display_order") or idx)
        if item_type == "github":
            projects.append(
                PortfolioProject(
                    id=str(item.get("id") or _new_id()),
                    title=title,
                    description=description,
                    image_url=image_url,
                    repo_url=url or None,
                    display_order=order,
                )
            )
            social.append(
                PortfolioSocialLink(
                    id=_new_id(),
                    platform="github",
                    label=title,
                    url=url,
                    display_order=order,
                )
            )
        else:
            projects.append(
                PortfolioProject(
                    id=str(item.get("id") or _new_id()),
                    title=title,
                    description=description,
                    image_url=image_url,
                    demo_url=url or None,
                    display_order=order,
                )
            )
    content = PortfolioContent(
        display_name=display_name,
        headline=headline,
        summary=bio,
        about=bio,
        projects=projects,
        social_links=social,
    )
    return PortfolioRevision(content=content)
