"""Pydantic request/response schemas for manual job entries (Module 4, Module F)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateManualJobEntryRequest(BaseModel):
    title: str = Field(max_length=255)
    company: str = Field(max_length=255)
    location: str | None = Field(default=None, max_length=255)
    source_label: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=2048)
    notes: str | None = Field(default=None, max_length=2000)


class ManualJobEntryResponse(BaseModel):
    id: str
    title: str
    company: str
    location: str | None
    source_label: str | None
    source_url: str | None
    notes: str | None
    job_match_id: str  # the auto-created tracker row's id — returned so the
    # frontend can navigate straight to the tracker entry
    created_at: datetime
