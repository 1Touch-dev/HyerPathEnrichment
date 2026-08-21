"""HTTP request/response schemas for the application tracker module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ApplicationStatus = Literal["new", "applied", "replied", "interview", "offer", "rejected"]
_ALL_STATUSES: tuple[ApplicationStatus, ...] = (
    "new",
    "applied",
    "replied",
    "interview",
    "offer",
    "rejected",
)


class TrackedMatchResponse(BaseModel):
    match_id: str
    job_posting_id: str
    title: str
    company: str
    location: str | None
    remote: bool
    source_url: str | None
    overall_score: float | None  # None for manual entries (Module F) — the
    # 0.0 sentinel stored on the row is never
    # surfaced to the frontend as a literal score
    application_status: ApplicationStatus
    apply_clicked_at: datetime | None
    applied_at: datetime | None
    status_updated_at: datetime | None
    created_at: datetime
    # Module D forward-reference: null until Module D lands; present in the
    # response shape from day one so the frontend tracker card doesn't need a
    # second schema version once interview scheduling ships.
    next_interview_at: datetime | None = None


class TrackedMatchListResponse(BaseModel):
    matches: list[TrackedMatchResponse]
    total: int
    limit: int
    offset: int
    counts_by_status: dict[ApplicationStatus, int]  # for tab/column badges


class UpdateApplicationStatusRequest(BaseModel):
    application_status: ApplicationStatus
