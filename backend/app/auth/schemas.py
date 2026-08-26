"""Pydantic schemas for authentication."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)


class UserRead(BaseModel):
    """User response schema (public profile)."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    avatar_url: str | None = None
    oauth_provider: str | None = None
    is_verified: bool
    is_active: bool
    is_superuser: bool
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    """User registration schema."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    # Staff invite token (machine-1-tenancy-core/05-org-invite-flow.md). An invalid
    # or expired token never hard-fails registration -- it just falls back to a
    # normal candidate signup with a warning in the response.
    invite_token: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Validate email format with regex."""
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email format")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Basic password strength validation."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseModel):
    """User profile update schema."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    avatar_url: str | None = Field(None, max_length=1024)
    password: str | None = Field(None, min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str | None) -> str | None:
        """Basic password strength validation."""
        if v is None:
            return v
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    """Login credentials."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response with user info."""

    user: UserRead
    message: str = "Login successful"


class RefreshTokenRequest(BaseModel):
    """Refresh token rotation request."""

    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Refresh token response with new tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class VerifyEmailRequest(BaseModel):
    """Email verification request."""

    token: str


class ResendVerificationRequest(BaseModel):
    """Resend verification email request."""

    email: EmailStr


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
    detail: dict[str, Any] | None = None


class RegisterResponse(MessageResponse):
    """Response for POST /auth/register only. Adds an optional `warning` field so
    a registration that fell back from an invalid/expired invite token can surface
    that to the caller without breaking existing callers that only read `.message`
    -- see machine-1-tenancy-core/05-org-invite-flow.md. When there is no invite
    token at all, `warning` stays None (same default MessageResponse callers have
    always seen for the `message`/`detail` fields)."""

    warning: str | None = None
