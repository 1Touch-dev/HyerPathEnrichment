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
    name: str
    address: str
    website: str
    rating: float
    phone: str
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
