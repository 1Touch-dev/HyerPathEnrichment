"""Business logic for LinkedIn sourcing leads (manual data-entry form only —
see 12-linkedin-sourcing-intern-multilogin.md's legal-risk section). This is a
simple insert/list/review CRUD, not a workflow with side effects: logging a
lead is not itself contacting anyone, so there is no suppression check here
(unlike `06`'s `enqueue_send_task`) — suppression is checked later, at
whatever point a recruiter actually initiates outreach using this lead's
`linkedin_profile_url` via `06`'s existing LinkedIn-send task-queue flow. This
module does not call into or import `06`'s files."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.identifiers import linkedin_slug_from_identifier
from app.modules.documents.models import CvChatSession
from app.modules.linkedin_sourcing import repository
from app.modules.linkedin_sourcing.models import SourcedCandidateLead
from app.modules.linkedin_sourcing.schemas import (
    CreateSourcedLeadRequest,
    ReviewSourcedLeadRequest,
    SourcedLeadResponse,
)


def _normalize_profile_url(url: str) -> str:
    slug = linkedin_slug_from_identifier(url)
    if slug is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="linkedin_profile_url must be a https LinkedIn /in/{slug} profile URL",
        )
    return f"https://www.linkedin.com/in/{slug}"


async def create_lead(
    db: AsyncSession, *, sourced_by: UUID, body: CreateSourcedLeadRequest
) -> SourcedLeadResponse:
    """Simple insert — this is a data-entry form, not a workflow with side
    effects. No suppression check here (unlike 06's enqueue_send_task) since
    logging a lead is not itself contacting anyone; suppression is checked later,
    at whatever point a recruiter actually initiates outreach using this lead's
    linkedin_profile_url (06's existing enqueue_send_task already does this for
    LinkedIn sends — this chunk does not duplicate that check)."""
    if sourced_by is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="An authenticated caller identity is required to log a sourced lead",
        )
    normalized_url = _normalize_profile_url(body.linkedin_profile_url)

    lead = SourcedCandidateLead(
        sourced_by=sourced_by,
        full_name=body.full_name,
        headline=body.headline,
        location=body.location,
        linkedin_profile_url=normalized_url,
        target_role=body.target_role,
        notes=body.notes,
    )
    lead = await repository.create(db, lead)
    return SourcedLeadResponse.model_validate(lead)


async def list_leads(db: AsyncSession, *, status: str | None = None) -> list[SourcedLeadResponse]:
    """Visible to any recruiter (not scoped to sourced_by — the whole point is a
    shared queue of leads for any recruiter to review, mirroring 08's shared-pool
    philosophy: sourcing an intern's lead does not make it 'that intern's lead'
    in an access-restrictive sense any more than assigning a candidate does)."""
    leads = await repository.list_all(db, status=status)
    return [SourcedLeadResponse.model_validate(lead) for lead in leads]


async def review_lead(
    db: AsyncSession, *, lead_id: UUID, reviewer_id: UUID, body: ReviewSourcedLeadRequest
) -> SourcedLeadResponse:
    lead = await repository.get_by_id(db, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    lead = await repository.mark_reviewed(db, lead, reviewer_id=reviewer_id, new_status=body.status)
    return SourcedLeadResponse.model_validate(lead)


async def mark_lead_converted(
    db: AsyncSession, *, lead_id: UUID, user_id: UUID
) -> SourcedLeadResponse:
    """Link a sourced lead to the real `User` row it converted into, once that
    person has completed the existing CV-chat qualification flow (see
    12-linkedin-sourcing-intern-multilogin.md's "Qualification path:
    SourcedCandidateLead -> User"). Reuses `CvChatSession.status == "completed"`
    — the same completeness gate every other candidate goes through — rather
    than building a second qualification mechanism.

    Does not touch/overwrite `status`: conversion is an additional fact
    recorded alongside whatever status the lead already has."""
    lead = await repository.get_by_id(db, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    result = await db.execute(
        select(CvChatSession).where(
            CvChatSession.user_id == user_id, CvChatSession.status == "completed"
        )
    )
    if result.scalars().first() is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Target user has not completed CV-chat qualification yet",
        )

    lead = await repository.mark_converted(
        db, lead, user_id=user_id, converted_at=datetime.now(UTC)
    )
    return SourcedLeadResponse.model_validate(lead)
