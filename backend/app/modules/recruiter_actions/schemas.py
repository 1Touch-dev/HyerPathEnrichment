from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApplyForCandidateRequest(BaseModel):
    candidate_user_id: UUID
    job_match_id: UUID
    recruiter_note: str | None = Field(default=None, max_length=1000)


class SuggestRoleRequest(BaseModel):
    candidate_user_id: UUID
    job_match_id: UUID
    recruiter_note: str | None = Field(default=None, max_length=1000)


class PendingActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    candidate_user_id: UUID
    recruiter_user_id: UUID
    job_match_id: UUID
    status: str
    recruiter_note: str | None
    created_at: datetime


class RoleSuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    candidate_user_id: UUID
    recruiter_user_id: UUID
    job_match_id: UUID
    status: str
    recruiter_note: str | None
    created_at: datetime


class RecruiterActionModeUpdateRequest(BaseModel):
    recruiter_action_mode: str = Field(..., pattern="^(autonomous|approval_required)$")


class RespondToSuggestionRequest(BaseModel):
    accept: bool
