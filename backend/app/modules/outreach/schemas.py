from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

OutreachMessageType = Literal["email", "linkedin", "generic", "custom"]
OutreachStrategy = Literal["direct_pitch", "value_first", "curiosity", "warm_referral"]
OutreachRoleType = Literal["technical", "non_technical"]
OutreachSeniority = Literal["junior", "senior"]


class OutreachDraftRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    recipient_role_title: str | None = Field(default=None, max_length=255)
    job_match_id: str | None = None
    # Optional pasted JD — when set, the worker uses this text instead of looking
    # up JobPosting.description_raw via job_match_id (still allowed together so
    # swipe drafts keep the match id for audit while a paste can override the text).
    job_description: str | None = Field(default=None, min_length=50, max_length=20_000)
    document_id: str  # which CV to draw candidate context from
    message_type: OutreachMessageType = "email"
    strategy: OutreachStrategy = "direct_pitch"
    referral_context: str | None = Field(
        default=None,
        max_length=500,
        description="Required when strategy='warm_referral'; validated in the service "
        "layer, mirroring custom_instruction's own conditional-requirement pattern below.",
    )
    role_type: OutreachRoleType | None = None
    seniority: OutreachSeniority | None = None
    recipient_email: str | None = Field(
        default=None,
        max_length=320,
        description="Required when message_type='email' (CAN-SPAM suppression check + "
        "physical-address footer only apply to actual email sends); validated in the "
        "service layer, same conditional-requirement pattern as custom_instruction/"
        "referral_context above.",
    )
    recipient_linkedin_url: str | None = Field(
        default=None,
        max_length=512,
        description="Required when message_type='linkedin' — the profile a human operator "
        "is shown when working the resulting LinkedInSendTask; validated in the service "
        "layer, same conditional-requirement pattern as recipient_email above.",
    )
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
    strategy: OutreachStrategy
    recipient_email: str | None
    recipient_linkedin_url: str | None
    sent_at: datetime | None
    created_at: datetime
    research_degraded: bool


class OutreachListResponse(BaseModel):
    messages: list[OutreachMessageResponse]


class OutreachEditRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=10000)


CompanyTier = Literal["premium", "outsourcing"]


class SetCompanyTierRequest(BaseModel):
    """``notes`` intentionally stays a plain ``str | None`` field rather than a
    custom sentinel wrapper type. Pydantic v2 already tracks, per-instance,
    which fields were actually present in the parsed request body via
    ``model_fields_set`` — the router's ``set_company_tier`` endpoint checks
    ``"notes" in body.model_fields_set`` to distinguish "the client omitted
    ``notes`` entirely" (leave any existing note untouched) from "the client
    explicitly sent ``notes: null``/an empty string" (clear/overwrite it).
    Reusing that native mechanism avoids inventing a parallel sentinel type
    just for this one optional field."""

    company_name: str = Field(..., min_length=1, max_length=255)
    tier: CompanyTier
    notes: str | None = Field(default=None)


class CompanyTierResponse(BaseModel):
    company_name: str
    tier: CompanyTier
    notes: str | None
    updated_at: datetime
