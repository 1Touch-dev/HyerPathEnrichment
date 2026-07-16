from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Postgres: jsonb; SQLite (local/tests): json. Single ORM type for both dialects.
JsonDoc = JSONB().with_variant(JSON(), "sqlite")


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
    purged = "purged"


class AuditEventType(StrEnum):
    opt_out = "opt_out"
    dsar_created = "dsar_created"
    dsar_completed = "dsar_completed"
    enrichment_suppressed = "enrichment_suppressed"
    data_purged = "data_purged"
    enrichment_completed = "enrichment_completed"


class DsarType(StrEnum):
    access = "access"
    deletion = "deletion"


class DsarStatus(StrEnum):
    pending = "pending"
    completed = "completed"
    rejected = "rejected"


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


class EnrichmentJobListItem(BaseModel):
    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    request_payload: dict[str, Any] = Field(default_factory=dict)
    identifier_summary: str = ""


class EnrichmentJobListResponse(BaseModel):
    jobs: list[EnrichmentJobListItem]
    total: int
    limit: int
    offset: int


class SuppressionRequest(BaseModel):
    identifier: str
    reason: str | None = None


class SuppressionCheckResponse(BaseModel):
    identifier: str
    suppressed: bool


class HealthResponse(BaseModel):
    status: str
    service: str


class DsarRequest(BaseModel):
    identifier: str
    request_type: DsarType
    notes: str | None = None


class DsarResponse(BaseModel):
    id: str
    status: DsarStatus
    request_type: DsarType
    created_at: datetime
    completed_at: datetime | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"job_{uuid4().hex}")
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.queued.value, nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    dossier_payload: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    identifier_hashes: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SuppressionRecord(Base):
    __tablename__ = "suppression_list"

    identifier_hash: Mapped[str] = mapped_column(String(128), primary_key=True)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DsarRecord(Base):
    __tablename__ = "dsar_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    identifier_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    request_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=DsarStatus.pending.value, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PhotoCacheRecord(Base):
    __tablename__ = "photo_cache"

    slug_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    asset_key: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    asset_url: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
