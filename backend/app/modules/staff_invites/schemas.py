"""HTTP schemas for the staff_invites module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StaffInviteCreate(BaseModel):
    email: EmailStr
    role_name: str = Field(default="recruiter", max_length=64)


class StaffInviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role_name: str
    expires_at: datetime
    accepted_at: datetime | None


class PublicStaffInviteResponse(BaseModel):
    """Response for GET /api/staff-invites/{token} -- unauthenticated, so this must
    leak nothing beyond what a pending-signup UI genuinely needs to display."""

    invited_by_name: str | None
    role_name: str
    email: str
    expires_at: datetime
