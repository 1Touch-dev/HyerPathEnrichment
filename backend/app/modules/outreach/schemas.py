from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OutreachDraftRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    recipient_role_title: str | None = Field(default=None, max_length=255)
    job_match_id: str | None = None
    document_id: str  # which CV to draw candidate context from


class OutreachMessageResponse(BaseModel):
    message_id: str
    company_name: str
    recipient_role_title: str | None
    subject: str
    body: str
    status: str
    sent_at: datetime | None
    created_at: datetime


class OutreachListResponse(BaseModel):
    messages: list[OutreachMessageResponse]


class OutreachEditRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=10000)
