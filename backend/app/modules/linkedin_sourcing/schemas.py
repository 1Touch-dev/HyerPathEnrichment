"""Pydantic schemas for LinkedIn sourcing leads. `linkedin_profile_url` is a
plain validated string (max-length + basic format check in the service layer),
not a strict `HttpUrl` type — see 12-linkedin-sourcing-intern-multilogin.md's
'just enough validation, no over-engineering' note."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateSourcedLeadRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    headline: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=255)
    linkedin_profile_url: str = Field(..., max_length=512)
    target_role: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class SourcedLeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sourced_by: UUID | None
    full_name: str
    headline: str | None
    location: str | None
    linkedin_profile_url: str
    target_role: str | None
    notes: str | None
    status: str
    created_at: datetime


class ReviewSourcedLeadRequest(BaseModel):
    status: str = Field(..., pattern="^(reviewed|contacted|dismissed)$")
