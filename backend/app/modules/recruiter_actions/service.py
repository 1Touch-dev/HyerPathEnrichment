"""Business logic for recruiter-initiated apply/suggest actions on behalf of a
candidate (machine-2/09). See 09-recruiter-initiated-apply-and-suggest.md for
the full design, including why recruiter_action_mode gates "apply" but not
"suggest role".
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.modules.documents.models import CandidateDocument
from app.modules.job_matching import push
from app.modules.job_matching.models import JobMatch
from app.modules.job_matching.repository import list_subscriptions_for_user
from app.modules.recruiter_actions.models import PendingRecruiterAction, RoleSuggestion
from app.modules.recruiter_actions.repository import (
    get_pending_action_by_id,
    get_role_suggestion_by_id,
)
from app.modules.recruiter_actions.schemas import (
    ApplyForCandidateRequest,
    PendingActionResponse,
    RoleSuggestionResponse,
    SuggestRoleRequest,
)

logger = logging.getLogger(__name__)


async def _get_user_or_404(db: AsyncSession, user_id: UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return user


async def _get_job_match_for_candidate(
    db: AsyncSession, job_match_id: UUID, candidate_user_id: UUID
) -> JobMatch:
    result = await db.execute(
        select(JobMatch).where(JobMatch.id == job_match_id, JobMatch.user_id == candidate_user_id)
    )
    match = result.scalar_one_or_none()
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job match not found for this candidate",
        )
    return match


async def _has_processed_cv(db: AsyncSession, candidate_user_id: UUID) -> bool:
    """Mirrors OutreachService.request_draft's "processed CV required" check
    (document.processing_status != "completed" -> 409), but scans the
    candidate's most recent document rather than requiring a specific
    document_id, since approve_pending_action has no document_id parameter."""
    result = await db.execute(
        select(CandidateDocument)
        .where(
            CandidateDocument.user_id == candidate_user_id,
            CandidateDocument.processing_status == "completed",
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _notify_candidate_push(
    db: AsyncSession, candidate: User, payload: dict[str, Any]
) -> None:
    """Best-effort push notification, reusing job_matching's existing
    push-subscription plumbing (fail-soft, never raises — mirrors
    interview_scheduling/service.py's _send_scheduled_notification convention).

    Both push and email notifications are sent for these events — see
    `_notify_candidate_email` below for the email half, dispatched via the
    same `enqueue_email` convention job_matching.py uses for its digest email.
    """
    try:
        subs = await list_subscriptions_for_user(db, candidate.id)
        for sub in subs:
            await push.send_push_notification(sub, payload)
    except Exception:
        logger.warning("recruiter_actions: push notification failed", exc_info=True)


def _notify_candidate_email(template: str, candidate: User, context: dict[str, Any]) -> None:
    """Best-effort email notification, fail-soft like `_notify_candidate_push`
    above — an email-send failure must never break the apply/suggest flow.
    Dispatched via `enqueue_email`, the same async-dispatch convention
    job_matching.py's `_send_match_digest_async` uses for candidate-facing
    notification emails.
    """
    try:
        from app.workers.queue import enqueue_email

        enqueue_email(template=template, recipient=candidate.email, context=context)
    except Exception:
        logger.warning("recruiter_actions: email notification failed", exc_info=True)


def _to_pending_response(action: PendingRecruiterAction) -> PendingActionResponse:
    return PendingActionResponse.model_validate(action)


def _to_suggestion_response(suggestion: RoleSuggestion) -> RoleSuggestionResponse:
    return RoleSuggestionResponse.model_validate(suggestion)


async def apply_for_candidate(
    db: AsyncSession, *, recruiter: User, body: ApplyForCandidateRequest
) -> dict[str, Any]:
    """Branches on the candidate's CURRENT recruiter_action_mode (re-read at
    call-time, not cached from anywhere) — if 'autonomous', apply immediately by
    updating the JobMatch row (mirroring the existing self-apply path's own
    application_status/applied_at write, see job_matching's own apply-tracking
    convention); if 'approval_required' (default), create a PendingRecruiterAction
    row instead and notify the candidate that a recruiter wants to apply on their
    behalf.
    """
    candidate = await _get_user_or_404(db, body.candidate_user_id)
    job_match = await _get_job_match_for_candidate(db, body.job_match_id, candidate.id)

    if candidate.recruiter_action_mode == "autonomous":
        now = datetime.now(UTC)
        job_match.application_status = "applied"
        job_match.applied_at = now
        job_match.status_updated_at = now
        await db.commit()
        await db.refresh(job_match)
        await _notify_candidate_push(
            db,
            candidate,
            {
                "event": "recruiter_applied_for_you",
                "job_match_id": str(job_match.id),
            },
        )
        return {
            "mode": "autonomous",
            "status": "applied",
            "job_match_id": str(job_match.id),
        }

    pending = PendingRecruiterAction(
        candidate_user_id=candidate.id,
        recruiter_user_id=recruiter.id,
        action_type="apply",
        job_match_id=job_match.id,
        recruiter_note=body.recruiter_note,
    )
    db.add(pending)
    await db.commit()
    await db.refresh(pending)
    await _notify_candidate_push(
        db,
        candidate,
        {
            "event": "recruiter_action_pending",
            "pending_action_id": str(pending.id),
            "job_match_id": str(job_match.id),
        },
    )
    _notify_candidate_email(
        "recruiter_action_pending",
        candidate,
        {
            "first_name": candidate.first_name,
            "pending_action_id": str(pending.id),
            "job_match_id": str(job_match.id),
        },
    )
    return {
        "mode": "approval_required",
        "status": "pending",
        "pending_action": _to_pending_response(pending),
    }


async def approve_pending_action(
    db: AsyncSession, *, candidate: User, action_id: UUID
) -> PendingActionResponse:
    """Candidate-only (action.candidate_user_id must equal candidate.id, checked
    here — 403 otherwise). Re-verifies action.status == 'pending' (409 if already
    decided) before applying the same JobMatch write apply_for_candidate's
    autonomous branch would have made directly."""
    action = await get_pending_action_by_id(db, action_id)
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pending action not found"
        )
    if action.candidate_user_id != candidate.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to act on this pending action",
        )
    if action.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pending action already {action.status}",
        )

    if not await _has_processed_cv(db, candidate.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A processed CV is required"
        )

    match_result = await db.execute(select(JobMatch).where(JobMatch.id == action.job_match_id))
    job_match = match_result.scalar_one_or_none()
    if job_match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job match not found")

    now = datetime.now(UTC)
    job_match.application_status = "applied"
    job_match.applied_at = now
    job_match.status_updated_at = now
    action.status = "approved"
    action.decided_at = now
    await db.commit()
    await db.refresh(action)
    return _to_pending_response(action)


async def reject_pending_action(
    db: AsyncSession, *, candidate: User, action_id: UUID
) -> PendingActionResponse:
    action = await get_pending_action_by_id(db, action_id)
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pending action not found"
        )
    if action.candidate_user_id != candidate.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to act on this pending action",
        )
    if action.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pending action already {action.status}",
        )

    action.status = "rejected"
    action.decided_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(action)
    return _to_pending_response(action)


async def suggest_role(
    db: AsyncSession, *, recruiter: User, body: SuggestRoleRequest
) -> RoleSuggestionResponse:
    """Always creates a RoleSuggestion row and notifies the candidate, regardless
    of recruiter_action_mode — see Goal section for why suggest is never gated by
    this preference."""
    candidate = await _get_user_or_404(db, body.candidate_user_id)
    job_match = await _get_job_match_for_candidate(db, body.job_match_id, candidate.id)

    suggestion = RoleSuggestion(
        candidate_user_id=candidate.id,
        recruiter_user_id=recruiter.id,
        job_match_id=job_match.id,
        recruiter_note=body.recruiter_note,
    )
    db.add(suggestion)
    await db.commit()
    await db.refresh(suggestion)
    await _notify_candidate_push(
        db,
        candidate,
        {
            "event": "role_suggested",
            "suggestion_id": str(suggestion.id),
            "job_match_id": str(job_match.id),
        },
    )
    _notify_candidate_email(
        "role_suggested",
        candidate,
        {
            "first_name": candidate.first_name,
            "suggestion_id": str(suggestion.id),
            "job_match_id": str(job_match.id),
        },
    )
    return _to_suggestion_response(suggestion)


async def respond_to_suggestion(
    db: AsyncSession, *, candidate: User, suggestion_id: UUID, accept: bool
) -> RoleSuggestionResponse:
    suggestion = await get_role_suggestion_by_id(db, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")
    if suggestion.candidate_user_id != candidate.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to act on this suggestion",
        )
    if suggestion.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Suggestion already {suggestion.status}",
        )

    suggestion.status = "accepted" if accept else "dismissed"
    suggestion.responded_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(suggestion)
    return _to_suggestion_response(suggestion)


async def update_recruiter_action_mode(db: AsyncSession, *, candidate: User, mode: str) -> None:
    """Candidate's own self-service preference update — no permission gate beyond
    authentication, same 'caller acting on their own row' convention as 08's
    list_my_candidates."""
    candidate.recruiter_action_mode = mode
    await db.commit()
