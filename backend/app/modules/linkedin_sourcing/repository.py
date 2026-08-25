"""Data-access layer for LinkedIn sourcing leads. Plain CRUD over
`SourcedCandidateLead` — no LinkedIn network calls anywhere in this module."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.linkedin_sourcing.models import SourcedCandidateLead


async def create(db: AsyncSession, lead: SourcedCandidateLead) -> SourcedCandidateLead:
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


async def get_by_id(db: AsyncSession, lead_id: UUID) -> SourcedCandidateLead | None:
    result = await db.execute(
        select(SourcedCandidateLead).where(SourcedCandidateLead.id == lead_id)
    )
    return result.scalar_one_or_none()


async def list_all(db: AsyncSession, *, status: str | None = None) -> list[SourcedCandidateLead]:
    """Shared, non-access-restrictive queue — not scoped to `sourced_by`."""
    query = select(SourcedCandidateLead).order_by(SourcedCandidateLead.created_at.desc())
    if status is not None:
        query = query.where(SourcedCandidateLead.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


async def mark_reviewed(
    db: AsyncSession, lead: SourcedCandidateLead, *, reviewer_id: UUID, new_status: str
) -> SourcedCandidateLead:
    lead.status = new_status
    lead.reviewed_by = reviewer_id
    lead.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(lead)
    return lead
