"""HTTP schemas for the staff_invites module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class StaffInviteCreate(BaseModel):
    email: EmailStr
    role_name: Literal["recruiter"] = Field(default="recruiter")
    confirmation_email: EmailStr
    mfa_code: SecretStr = Field(min_length=6, max_length=8)


class StaffInviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role_name: str
    expires_at: datetime
    accepted_at: datetime | None
    # Returned only by the creation call for a newly issued invite. Stored
    # invite reads and idempotent reuse never expose the bearer credential.
    invite_token: str | None = None


class PublicStaffInviteResponse(BaseModel):
    """Response for GET /api/staff-invites/{token} -- unauthenticated, so this must
    leak nothing beyond what a pending-signup UI genuinely needs to display."""

    invited_by_name: str | None
    role_name: str
    email: str
    expires_at: datetime
