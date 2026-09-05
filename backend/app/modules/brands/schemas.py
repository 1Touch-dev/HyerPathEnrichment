"""HTTP schemas for the brands module. Presentation-only fields — see
docs/adr/0019-tenancy-model.md; no field here is ever used as an access-scoping value."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BrandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    custom_domain: str | None = None
    chatbot_config: dict[str, Any] | None = None
    landing_page_tier_config: dict[str, Any] | None = None


class BrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    custom_domain: str | None
    chatbot_config: dict[str, Any] | None
    landing_page_tier_config: dict[str, Any] | None
    is_active: bool
    created_at: datetime


# Recruiter-candidate assignment schemas (machine-2-parallel-tracks/
# 08-recruiter-candidate-assignment.md). Ownership marker only — see
# docs/adr/0019-tenancy-model.md Decision §4; never used for access control.
#
# Deviation from the original spec doc: the spec's `AssignmentResponse`
# includes `assigned_by`/`assigned_at` fields, but `RecruiterCandidateAssignment`
# already exists in models.py (added by machine-1-tenancy-core/02) with only
# `id`, `recruiter_user_id`, `candidate_user_id`, `created_at` -- no
# `assigned_by` column. Since models.py is out of this chunk's edit scope,
# this response mirrors the model's real columns instead of the spec's
# illustrative shape.


class AssignCandidateRequest(BaseModel):
    candidate_user_id: UUID
    recruiter_user_id: UUID


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recruiter_user_id: UUID
    candidate_user_id: UUID
    created_at: datetime


class MyCandidatesListResponse(BaseModel):
    assignments: list[AssignmentResponse]
