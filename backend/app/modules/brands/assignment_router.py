"""HTTP routes for recruiter-candidate assignment
(machine-2-parallel-tracks/08-recruiter-candidate-assignment.md). Mirrors
`app/modules/admin/roles_router.py`'s `require_permission`/`EnvelopeAPIRoute`
pattern.

Route shapes (per the spec's own router.py section, which explicitly leaves
the DELETE path's identity resolution to the implementer's choice, "document
whichever is chosen"):

    POST   /api/recruiter-assignments                      -> assign_candidate
    DELETE /api/recruiter-assignments/{candidate_user_id}   -> unassign_candidate
    GET    /api/recruiter-assignments/my-candidates         -> list_my_candidates

Chosen shape for DELETE: `recruiter_user_id` is always the authenticated
caller (self-unassign), never a request body value -- so a recruiter can only
detach themselves from a candidate, not another recruiter. This needs no
elevated permission beyond authentication, matching the spec's note that a
recruiter unassigning *themselves* may be allowed without the
`recruiter_assignments:write` gate. An admin/team-lead wanting to reassign a
candidate away from a different recruiter calls `assign_candidate` for the
new recruiter instead (gated by `recruiter_assignments:write`), rather than
this endpoint unassigning on another recruiter's behalf.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin.permissions import require_permission
from app.modules.brands import assignment_service
from app.modules.brands.schemas import (
    AssignCandidateRequest,
    AssignmentResponse,
    MyCandidatesListResponse,
)

router = APIRouter(
    prefix="/api/recruiter-assignments", tags=["brands"], route_class=EnvelopeAPIRoute
)


@router.post("", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_candidate(
    body: AssignCandidateRequest,
    user: User = Depends(require_permission("recruiter_assignments", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> AssignmentResponse:
    return await assignment_service.assign_candidate(db, actor=user, body=body)


@router.delete("/{candidate_user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def unassign_candidate(
    candidate_user_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await assignment_service.unassign_candidate(
        db,
        actor=current_user,
        recruiter_user_id=current_user.id,
        candidate_user_id=candidate_user_id,
    )


@router.get("/my-candidates", response_model=MyCandidatesListResponse)
async def list_my_candidates(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> MyCandidatesListResponse:
    return await assignment_service.list_my_candidates(db, recruiter_user_id=current_user.id)
