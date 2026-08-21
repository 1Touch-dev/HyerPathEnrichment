"""Thin HTTP layer for JD-tailored interview practice.

Per RULE.md "Routes are thin": auth, parse request, call service, return.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.core.api_route import EnvelopeAPIRoute
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.modules.jd_practice.schemas import JdPracticeRequest, JdPracticeResponse
from app.modules.jd_practice.service import get_jd_tailored_questions

router = APIRouter(prefix="/api/jd-practice", tags=["jd-practice"], route_class=EnvelopeAPIRoute)


@router.post("/questions", response_model=JdPracticeResponse)
async def get_jd_practice_questions(
    request: JdPracticeRequest,
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> JdPracticeResponse:
    return await get_jd_tailored_questions(db, user.id, request, settings)
