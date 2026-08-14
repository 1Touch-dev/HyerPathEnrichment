"""Thin HTTP layer for the question bank / personalized generation API.

Per RULE.md "Routes are thin": auth, parse request, call service, return.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.core.api_route import EnvelopeAPIRoute
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.modules.questions.schemas import QuestionListResponse, QuestionRequest
from app.modules.questions.service import get_questions

router = APIRouter(prefix="/api/questions", tags=["questions"], route_class=EnvelopeAPIRoute)


@router.post("", response_model=QuestionListResponse)
async def list_questions(
    request: QuestionRequest,
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> QuestionListResponse:
    """Select (and, if needed, generate) interview questions for the current user."""
    return await get_questions(db, user.id, request, settings)
