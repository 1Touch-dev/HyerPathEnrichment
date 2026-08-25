"""FastAPI router for recruiter-initiated apply/suggest actions on behalf of a
candidate (machine-2/09).

Recruiter-facing endpoints (apply, suggest) require authentication only — no
require_permission gate beyond being a logged-in recruiter/staff account,
consistent with 08's "any recruiter can act on any candidate" model.

Deviation from spec: the plan asks for `PATCH /api/users/me/recruiter-action-mode`
to live "under the existing user-profile router if one exists". No such
self-service user-profile router exists in this codebase today (verified:
`auth/router.py` only exposes a read-only `GET /me`, and it is on this track's
do-not-touch list) — so that route is added here instead, under this module's
own router, rather than inventing a new profile router or touching
auth/router.py.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.recruiter_actions import repository, service
from app.modules.recruiter_actions.schemas import (
    ApplyForCandidateRequest,
    PendingActionResponse,
    RecruiterActionModeUpdateRequest,
    RespondToSuggestionRequest,
    RoleSuggestionResponse,
    SuggestRoleRequest,
)

router = APIRouter(
    prefix="/api/recruiter-actions", tags=["recruiter-actions"], route_class=EnvelopeAPIRoute
)

# Separate router (same file, not a dedicated new router file) so the literal
# `PATCH /api/users/me/recruiter-action-mode` path from the spec is preserved
# rather than nested under /api/recruiter-actions — see module docstring above.
users_router = APIRouter(prefix="/api/users", tags=["users"], route_class=EnvelopeAPIRoute)


@router.post("/apply")
async def apply_for_candidate(
    body: ApplyForCandidateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await service.apply_for_candidate(db, recruiter=current_user, body=body)


@router.post("/suggest", response_model=RoleSuggestionResponse)
async def suggest_role(
    body: SuggestRoleRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> RoleSuggestionResponse:
    return await service.suggest_role(db, recruiter=current_user, body=body)


@router.post("/pending/{action_id}/approve", response_model=PendingActionResponse)
async def approve_pending_action(
    action_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> PendingActionResponse:
    return await service.approve_pending_action(db, candidate=current_user, action_id=action_id)


@router.post("/pending/{action_id}/reject", response_model=PendingActionResponse)
async def reject_pending_action(
    action_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> PendingActionResponse:
    return await service.reject_pending_action(db, candidate=current_user, action_id=action_id)


@router.post("/suggestions/{suggestion_id}/respond", response_model=RoleSuggestionResponse)
async def respond_to_suggestion(
    suggestion_id: UUID,
    body: RespondToSuggestionRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> RoleSuggestionResponse:
    return await service.respond_to_suggestion(
        db, candidate=current_user, suggestion_id=suggestion_id, accept=body.accept
    )


@router.get("/pending", response_model=list[PendingActionResponse])
async def list_pending_actions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> list[PendingActionResponse]:
    actions = await repository.list_pending_actions_for_candidate(db, current_user.id)
    return [PendingActionResponse.model_validate(a) for a in actions]


@router.get("/suggestions", response_model=list[RoleSuggestionResponse])
async def list_suggestions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> list[RoleSuggestionResponse]:
    suggestions = await repository.list_role_suggestions_for_candidate(db, current_user.id)
    return [RoleSuggestionResponse.model_validate(s) for s in suggestions]


@users_router.patch("/me/recruiter-action-mode")
async def update_recruiter_action_mode(
    body: RecruiterActionModeUpdateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    await service.update_recruiter_action_mode(
        db, candidate=current_user, mode=body.recruiter_action_mode
    )
    return {"recruiter_action_mode": body.recruiter_action_mode}
