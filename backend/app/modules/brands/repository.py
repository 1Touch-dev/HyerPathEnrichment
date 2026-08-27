"""Data-access layer for brands. Plain async functions, not a class — matches
app/modules/portfolio/repository.py's style."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.brands.models import Brand, RecruiterCandidateAssignment


async def get_brand_by_id(db: AsyncSession, brand_id: UUID) -> Brand | None:
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    return result.scalar_one_or_none()


async def get_brand_by_slug(db: AsyncSession, slug: str) -> Brand | None:
    result = await db.execute(select(Brand).where(Brand.slug == slug))
    return result.scalar_one_or_none()


async def create_brand(db: AsyncSession, **fields: Any) -> Brand:
    brand = Brand(**fields)
    db.add(brand)
    await db.flush()
    return brand


async def list_active_brands(db: AsyncSession) -> list[Brand]:
    result = await db.execute(select(Brand).where(Brand.is_active.is_(True)))
    return list(result.scalars().all())


async def create_assignment(
    db: AsyncSession, *, recruiter_user_id: UUID, candidate_user_id: UUID
) -> RecruiterCandidateAssignment:
    """Idempotent by (recruiter_user_id, candidate_user_id) — return the existing row
    if the pair is already assigned rather than raising a unique-constraint error.
    Used by machine-2-parallel-tracks/08-recruiter-candidate-assignment.md."""
    result = await db.execute(
        select(RecruiterCandidateAssignment).where(
            RecruiterCandidateAssignment.recruiter_user_id == recruiter_user_id,
            RecruiterCandidateAssignment.candidate_user_id == candidate_user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    assignment = RecruiterCandidateAssignment(
        recruiter_user_id=recruiter_user_id, candidate_user_id=candidate_user_id
    )
    db.add(assignment)
    await db.flush()
    return assignment


async def list_assigned_candidate_ids(db: AsyncSession, recruiter_user_id: UUID) -> list[UUID]:
    """For 'my assigned candidates' views/reporting only — never used to restrict
    what a recruiter can query elsewhere."""
    result = await db.execute(
        select(RecruiterCandidateAssignment.candidate_user_id).where(
            RecruiterCandidateAssignment.recruiter_user_id == recruiter_user_id
        )
    )
    return list(result.scalars().all())


async def delete_assignment(
    db: AsyncSession, *, recruiter_user_id: UUID, candidate_user_id: UUID
) -> bool:
    """Idempotent unassign: returns False (no-op, not an error) if no matching
    row existed. Deleting this row only affects 'my assigned candidates' views
    and notification routing — see models.py's RecruiterCandidateAssignment
    docstring; it never cascades to or hides any other domain data."""
    result = await db.execute(
        select(RecruiterCandidateAssignment).where(
            RecruiterCandidateAssignment.recruiter_user_id == recruiter_user_id,
            RecruiterCandidateAssignment.candidate_user_id == candidate_user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return False
    await db.delete(existing)
    await db.flush()
    return True


async def list_assignments_for_recruiter(
    db: AsyncSession, recruiter_user_id: UUID
) -> list[RecruiterCandidateAssignment]:
    """Full assignment rows for a recruiter's 'my assigned candidates' view —
    see list_assigned_candidate_ids above for the ids-only variant used
    elsewhere; this one backs MyCandidatesListResponse's richer shape."""
    result = await db.execute(
        select(RecruiterCandidateAssignment).where(
            RecruiterCandidateAssignment.recruiter_user_id == recruiter_user_id
        )
    )
    return list(result.scalars().all())


async def list_assigned_recruiters_for_candidate(
    db: AsyncSession, candidate_user_id: UUID
) -> list[RecruiterCandidateAssignment]:
    """Read path for a future notification-dispatch chunk (see the spec's Goal
    §3) — not called by anything in this chunk itself, provided so that chunk
    doesn't have to add its own query against this table's raw columns."""
    result = await db.execute(
        select(RecruiterCandidateAssignment).where(
            RecruiterCandidateAssignment.candidate_user_id == candidate_user_id
        )
    )
    return list(result.scalars().all())
