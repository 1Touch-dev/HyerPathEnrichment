"""FastAPI router for ephemeral, on-demand resume tailoring (machine-2 track 10).

Both endpoints require authentication only (`VerifiedUser`), same as outreach's
own draft-request endpoint — no new permission resource needed; a candidate
tailoring their own resume needs no elevated permission. `document_id`/
`user_id` ownership is checked in the service layer exactly like every other
candidate-owned-document endpoint in this codebase.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.resume_tailoring.schemas import (
    TailoredResumeResultResponse,
    TailorResumeJobResponse,
    TailorResumeRequest,
)
from app.modules.resume_tailoring.service import get_tailoring_result, request_tailoring
from app.workers.queue import get_redis_connection

router = APIRouter(
    prefix="/api/resume-tailoring", tags=["resume-tailoring"], route_class=EnvelopeAPIRoute
)


@router.post("", response_model=TailorResumeJobResponse)
async def create_tailoring_request(
    body: TailorResumeRequest,
    current_user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> TailorResumeJobResponse:
    return await request_tailoring(
        db, user_id=current_user.id, body=body, redis_conn=get_redis_connection()
    )


@router.get("/{rq_job_id}", response_model=TailoredResumeResultResponse)
async def get_tailoring_result_endpoint(
    rq_job_id: str, current_user: VerifiedUser
) -> TailoredResumeResultResponse:
    return get_tailoring_result(rq_job_id, get_redis_connection())
