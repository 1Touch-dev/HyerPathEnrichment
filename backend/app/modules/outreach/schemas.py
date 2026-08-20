from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

OutreachMessageType = Literal["email", "linkedin", "generic", "custom"]


class OutreachDraftRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    recipient_role_title: str | None = Field(default=None, max_length=255)
    job_match_id: str | None = None
    document_id: str  # which CV to draw candidate context from
    message_type: OutreachMessageType = "email"
    custom_instruction: str | None = Field(
        default=None,
        max_length=1000,
        description="Required when message_type='custom'; validated in the service layer "
        "(not a Pydantic model_validator) since the requirement is conditional on another "
        "field's value — same pattern already used by JobPreferencesRequest's salary_max "
        "cross-field validator elsewhere in this codebase for the shape of the check, "
        "though this one is easier expressed as a plain service-layer guard.",
    )


class OutreachMessageResponse(BaseModel):
    message_id: str
    company_name: str
    recipient_role_title: str | None
    subject: str
    body: str
    status: str
    message_type: OutreachMessageType
    sent_at: datetime | None
    created_at: datetime
    research_degraded: bool


class OutreachListResponse(BaseModel):
    messages: list[OutreachMessageResponse]


class OutreachEditRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=10000)
