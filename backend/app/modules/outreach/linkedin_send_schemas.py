from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

LinkedInActionType = Literal["connection_request", "inmail", "direct_message"]
LinkedInTaskStatus = Literal["pending", "claimed", "completed", "skipped"]
LinkedInBatchStatus = Literal["pending", "running", "completed", "cancelled", "failed"]


class LinkedInSendTaskResponse(BaseModel):
    id: str
    outreach_message_id: str
    batch_id: str | None
    linkedin_profile_url: str
    action_type: LinkedInActionType
    status: LinkedInTaskStatus
    claimed_by: str | None
    claimed_at: datetime | None
    completed_at: datetime | None
    outcome_note: str | None
    created_at: datetime


class LinkedInTaskListResponse(BaseModel):
    tasks: list[LinkedInSendTaskResponse]


class CompleteLinkedInTaskRequest(BaseModel):
    outcome_note: str | None = Field(default=None, max_length=1000)


class SkipLinkedInTaskRequest(BaseModel):
    outcome_note: str | None = Field(default=None, max_length=1000)


class CreateLinkedInSendBatchRequest(BaseModel):
    multilogin_profile_id: str = Field(..., min_length=1, max_length=255)
    # Required — no unlimited option (see LinkedInSendBatch.max_sends_per_day's
    # docstring). Omitting this field is a 422, not a fallback to unlimited.
    max_sends_per_day: int = Field(..., gt=0)
    task_ids: list[UUID] = Field(
        default_factory=list,
        description="Existing pending LinkedInSendTask rows (batch_id IS NULL) to attach "
        "to this batch at creation time.",
    )


class LinkedInSendBatchResponse(BaseModel):
    id: str
    triggered_by: str | None
    multilogin_profile_id: str
    status: LinkedInBatchStatus
    max_sends_per_day: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
