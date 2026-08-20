"""Pydantic request/response schemas for interview scheduling (Module 4, Module D)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleInterviewRequest(BaseModel):
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    notes: str | None = Field(default=None, max_length=2000)


class InterviewScheduleResponse(BaseModel):
    id: str
    job_match_id: str
    scheduled_at: datetime
    duration_minutes: int
    notes: str | None
    ics_download_url: str
    google_calendar_link: str
    created_at: datetime
