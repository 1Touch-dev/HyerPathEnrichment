from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SocialHandle(BaseModel):
    platform: str
    username: str
    profile_url: str
    confidence: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerifiedEmail(BaseModel):
    value: str
    status: str
    confidence: float
    source: str


class ConfidenceBreakdown(BaseModel):
    label: str
    score: float
    evidence: list[str]


class JobListing(BaseModel):
    title: str
    company: str
    location: str
    remote: bool
    source: str


class BusinessProfile(BaseModel):
    # Core fields (existing)
    name: str
    address: str
    website: str
    rating: float
    phone: str

    # Location & identification
    category: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    place_id: str | None = None
    cid: str | None = None
    plus_code: str | None = None
    complete_address: str | None = None

    # Operations
    open_hours: str | None = None
    popular_times: str | None = None
    timezone: str | None = None
    status: str | None = None  # open/closed/temporary

    # Reviews & ratings
    review_count: int | None = None
    reviews_per_rating: dict[str, int] | None = None  # {"5": 120, "4": 45, ...}
    reviews_link: str | None = None
    user_reviews: list[dict[str, Any]] | None = None  # [{text, rating, timestamp}]

    # Media
    thumbnail: str | None = None
    images: list[str] | None = None
    street_view_url: str | None = None

    # Commerce
    price_range: str | None = None  # $, $$, $$$, $$$$
    reservations: str | None = None
    order_online: str | None = None
    menu: str | None = None
    credit_cards_accepted: str | None = None

    # Additional info
    description: str | None = None
    about: str | None = None
    owner: str | None = None
    emails: list[str] | None = None

    # Google Maps references
    link: str | None = None
    data_id: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)


class PhotoAsset(BaseModel):
    source: str
    asset_url: str
    captured_at: datetime
    confidence: float


class Dossier(BaseModel):
    photo: PhotoAsset | None = None
    handles: list[SocialHandle] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    verified_emails: list[VerifiedEmail] = Field(default_factory=list)
    github: dict[str, Any] = Field(default_factory=dict)
    coworkers: list[str] = Field(default_factory=list)
    jobs: list[JobListing] = Field(default_factory=list)
    business: BusinessProfile | None = None
    confidence: list[ConfidenceBreakdown] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
