"""Data-access layer for recruiter_actions. Workers import this, never service.py."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.recruiter_actions.models import PendingRecruiterAction, RoleSuggestion


async def get_pending_action_by_id(
    db: AsyncSession, action_id: UUID
) -> PendingRecruiterAction | None:
    result = await db.execute(
        select(PendingRecruiterAction).where(PendingRecruiterAction.id == action_id)
    )
    return result.scalar_one_or_none()


async def list_pending_actions_for_candidate(
    db: AsyncSession, candidate_user_id: UUID
) -> list[PendingRecruiterAction]:
    result = await db.execute(
        select(PendingRecruiterAction)
        .where(PendingRecruiterAction.candidate_user_id == candidate_user_id)
        .order_by(PendingRecruiterAction.created_at.desc())
    )
    return list(result.scalars().all())


async def get_role_suggestion_by_id(db: AsyncSession, suggestion_id: UUID) -> RoleSuggestion | None:
    result = await db.execute(select(RoleSuggestion).where(RoleSuggestion.id == suggestion_id))
    return result.scalar_one_or_none()


async def list_role_suggestions_for_candidate(
    db: AsyncSession, candidate_user_id: UUID
) -> list[RoleSuggestion]:
    result = await db.execute(
        select(RoleSuggestion)
        .where(RoleSuggestion.candidate_user_id == candidate_user_id)
        .order_by(RoleSuggestion.created_at.desc())
    )
    return list(result.scalars().all())
