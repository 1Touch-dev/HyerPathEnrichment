"""FastAPI router for the swipe deck. Nested under Module 1's /api/matches prefix (§4.3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.job_swipe.schemas import SwipeActionRequest, SwipeActionResponse, SwipeDeckResponse
from app.modules.job_swipe.service import JobSwipeService

router = APIRouter(prefix="/api/matches", tags=["job-swipe"], route_class=EnvelopeAPIRoute)


@router.get("/swipe-deck", response_model=SwipeDeckResponse)
async def get_swipe_deck(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> SwipeDeckResponse:
    """Next batch of unswiped matches, highest score first."""
    return await JobSwipeService(db).get_deck(current_user.id)


@router.post("/{match_id}/swipe", response_model=SwipeActionResponse)
async def swipe_match(
    match_id: str,
    body: SwipeActionRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> SwipeActionResponse:
    """Record (or overwrite) a swipe decision on one match."""
    return await JobSwipeService(db).swipe(current_user.id, match_id, body)
