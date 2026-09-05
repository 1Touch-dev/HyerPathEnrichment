"""Business-logic layer for recruiter-candidate assignment
(machine-2-parallel-tracks/08-recruiter-candidate-assignment.md). An ownership
marker only, NOT an access-control gate -- see docs/adr/0019-tenancy-model.md
Decision §4. Recording or omitting a row here never changes which candidates
a recruiter can search, view, or act on.

`assign_candidate`/on-behalf-of-another-recruiter `unassign_candidate` are
gated by require_permission("recruiter_assignments", "write") at the router
layer -- these functions themselves do not re-check permissions, following
the existing convention where router-level Depends() is the enforcement
point and service functions trust their caller (see roles_service.py's
create_role, which does the same)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.modules.brands import repository
from app.modules.brands.schemas import (
    AssignCandidateRequest,
    AssignmentResponse,
    MyCandidatesListResponse,
)


async def assign_candidate(
    db: AsyncSession, *, actor: User, body: AssignCandidateRequest
) -> AssignmentResponse:
    """`actor` is accepted (per the spec's service signature) for parity with
    a future audit trail, but is not persisted anywhere: the current
    `RecruiterCandidateAssignment` model (already existing, out of this
    chunk's edit scope) has no `assigned_by` column to record it in."""
    assignment = await repository.create_assignment(
        db, recruiter_user_id=body.recruiter_user_id, candidate_user_id=body.candidate_user_id
    )
    await db.commit()
    return AssignmentResponse.model_validate(assignment)


async def unassign_candidate(
    db: AsyncSession, *, actor: User, recruiter_user_id: UUID, candidate_user_id: UUID
) -> None:
    """No-op (not an error) if the pair was never assigned -- see
    repository.delete_assignment's docstring."""
    await repository.delete_assignment(
        db, recruiter_user_id=recruiter_user_id, candidate_user_id=candidate_user_id
    )
    await db.commit()


async def list_my_candidates(
    db: AsyncSession, *, recruiter_user_id: UUID
) -> MyCandidatesListResponse:
    """No permission gate beyond authentication -- a recruiter listing their
    own assignments is always allowed; this is the one read path that IS
    scoped to the caller, by caller-identity convenience, not by a security
    boundary hiding other candidates (a recruiter can still list/search all
    candidates via the existing unscoped candidate-listing endpoints
    elsewhere in the codebase)."""
    assignments = await repository.list_assignments_for_recruiter(db, recruiter_user_id)
    return MyCandidatesListResponse(
        assignments=[AssignmentResponse.model_validate(a) for a in assignments]
    )
