"""HTTP request/response schemas for the job matching module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

_NotificationChannel = Literal["email", "sms", "webhook", "push"]


def _default_notification_channels() -> list[_NotificationChannel]:
    return ["email"]


class JobPreferencesRequest(BaseModel):
    desired_roles: list[str] = Field(default_factory=list, max_length=20)
    desired_locations: list[str] = Field(default_factory=list, max_length=20)
    remote_preference: Literal["remote", "hybrid", "onsite"] | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str = Field(default="USD", max_length=10)
    notification_channels: list[_NotificationChannel] = Field(
        default_factory=_default_notification_channels
    )
    webhook_url: str | None = Field(default=None, max_length=2048)
    digest_frequency: Literal["daily", "weekly", "off"] = "daily"
    is_scan_enabled: bool = True

    @field_validator("salary_max")
    @classmethod
    def _max_gte_min(cls, v: int | None, info: ValidationInfo) -> int | None:
        salary_min = info.data.get("salary_min")
        if v is not None and salary_min is not None and v < salary_min:
            raise ValueError("salary_max must be >= salary_min")
        return v


class JobPreferencesResponse(JobPreferencesRequest):
    user_id: str
    source_document_id: str | None
    last_scanned_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobMatchResponse(BaseModel):
    match_id: str
    job_posting_id: str
    title: str
    company: str
    location: str | None
    remote: bool
    source: str
    source_url: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    overall_score: float
    score_breakdown: dict[str, float | bool]
    explanation: str | None
    is_new: bool  # notified_at is None
    viewed_at: datetime | None
    feedback: Literal["up", "down"] | None
    created_at: datetime


class JobMatchListResponse(BaseModel):
    matches: list[JobMatchResponse]
    total: int
    limit: int
    offset: int


class JobMatchFeedbackRequest(BaseModel):
    feedback: Literal["up", "down"]


class ScanTriggerResponse(BaseModel):
    message: str
    scan_enqueued: bool


class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(max_length=2048)
    p256dh: str
    auth: str


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(max_length=2048)
