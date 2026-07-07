from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RequestedTier(StrEnum):
    tier1 = "tier1"
    tier2 = "tier2"
    tier3 = "tier3"
    tier4 = "tier4"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    suppressed = "suppressed"


class EnrichmentRequest(BaseModel):
    email: str | None = None
    linkedin_url: str | None = None
    username: str | None = None
    company: str | None = None
    business: str | None = None
    job_search: str | None = None
    requested_tiers: list[RequestedTier] = Field(default_factory=lambda: list(RequestedTier))

    @model_validator(mode="after")
    def ensure_identifier(self) -> "EnrichmentRequest":
        if not any([
            self.email,
            self.linkedin_url,
            self.username,
            self.company,
            self.business,
            self.job_search,
        ]):
            raise ValueError("at least one identifier is required")
        return self


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


class EnrichmentJobResponse(BaseModel):
    id: str
    status: JobStatus
    dossier: Dossier


class SuppressionRequest(BaseModel):
    identifier: str
    reason: str | None = None


class SuppressionCheckResponse(BaseModel):
    identifier: str
    suppressed: bool


class HealthResponse(BaseModel):
    status: str
    service: str


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"job_{uuid4().hex}")
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.queued.value, nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    dossier_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SuppressionRecord(Base):
    __tablename__ = "suppression_list"

    identifier_hash: Mapped[str] = mapped_column(String(128), primary_key=True)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
