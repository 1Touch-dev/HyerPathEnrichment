"""Business logic for the swipe deck."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_matching.models import JobMatch
from app.modules.job_swipe.repository import (
    delete_swipe,
    get_last_swipe,
    get_unswiped_matches,
    record_swipe,
)
from app.modules.job_swipe.schemas import (
    SwipeableMatchResponse,
    SwipeActionRequest,
    SwipeActionResponse,
    SwipeDeckResponse,
)

_DECK_PAGE_SIZE = 20


class JobSwipeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_deck(self, user_id: UUID) -> SwipeDeckResponse:
        rows = await get_unswiped_matches(self.db, user_id, _DECK_PAGE_SIZE + 1)
        has_more = len(rows) > _DECK_PAGE_SIZE
        rows = rows[:_DECK_PAGE_SIZE]
        return SwipeDeckResponse(
            cards=[
                SwipeableMatchResponse(
                    match_id=str(m.id),
                    job_posting_id=str(p.id),
                    title=p.title,
                    company=p.company,
                    location=p.location,
                    remote=p.remote,
                    salary_min=p.salary_min,
                    salary_max=p.salary_max,
                    salary_currency=p.salary_currency,
                    overall_score=m.overall_score,
                    explanation=m.explanation,
                    created_at=m.created_at,
                )
                for m, p in rows
            ],
            has_more=has_more,
        )

    async def swipe(
        self, user_id: UUID, match_id: str, body: SwipeActionRequest
    ) -> SwipeActionResponse:
        result = await self.db.execute(
            select(JobMatch).where(JobMatch.id == UUID(match_id), JobMatch.user_id == user_id)
        )
        match = result.scalar_one_or_none()
        if not match:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

        action = await record_swipe(self.db, match.id, user_id, body.direction)
        return SwipeActionResponse(
            match_id=str(match.id), direction=action.direction, created_at=action.created_at
        )

    async def undo_last_swipe(self, user_id: UUID) -> SwipeActionResponse:
        """Undo the candidate's most recent swipe decision, restoring that card to the deck."""
        last_swipe = await get_last_swipe(self.db, user_id)
        if not last_swipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No previous swipe to undo"
            )

        restored = SwipeActionResponse(
            match_id=str(last_swipe.job_match_id),
            direction=last_swipe.direction,
            created_at=last_swipe.created_at,
        )
        await delete_swipe(self.db, last_swipe.id)
        return restored
