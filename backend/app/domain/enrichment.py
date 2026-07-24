from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.domain.dossier import Dossier
from app.domain.enums import DsarStatus, DsarType, JobStatus, RequestedTier


class EnrichmentRequest(BaseModel):
    email: str | None = None
    linkedin_url: str | None = None
    username: str | None = None
    company: str | None = None
    business: str | None = None
    job_search: str | None = None
    requested_tiers: list[RequestedTier] = Field(default_factory=lambda: list(RequestedTier))

    @model_validator(mode="after")
    def ensure_identifier(self) -> EnrichmentRequest:
        if not any(
            [
                self.email,
                self.linkedin_url,
                self.username,
                self.company,
                self.business,
                self.job_search,
            ]
        ):
            raise ValueError("at least one identifier is required")

        tiers = self.requested_tiers or list(RequestedTier)
        if RequestedTier.tier1 in tiers and not self.linkedin_url:
            raise ValueError("tier1 requires linkedin_url")
        if RequestedTier.tier2 in tiers and not self.username:
            raise ValueError("tier2 requires username")
        if RequestedTier.tier3 in tiers and not any(
            [
                self.username,
                self.email,
                self.company,
            ]
        ):
            raise ValueError("tier3 requires at least one of username, email, or company")
        if RequestedTier.tier4 in tiers and not any([self.job_search, self.business]):
            raise ValueError("tier4 requires at least one of job_search or business")

        return self


class EnrichmentJobResponse(BaseModel):
    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
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


class SignalListItem(BaseModel):
    id: str
    source: str
    watch_id: str
    title: str
    url: str
    timestamp: str | None = None
    created_at: datetime


class SignalListResponse(BaseModel):
    signals: list[SignalListItem]
    total: int
    limit: int
    offset: int
