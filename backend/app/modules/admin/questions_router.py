"""Admin interview-question moderation endpoints (Admin Module Phase 2 —
moderation layer, Module 3). Follows `job_postings_router.py`'s pattern of
inline Pydantic models rather than `schemas.py` (deliberately untouched by
every Batch-1 chunk, see plan)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_admin_moderation_rate_limit
from app.models import InterviewQuestion
from app.modules.admin.audit import record_admin_action
from app.modules.admin.pagination import decode_cursor, encode_cursor
from app.modules.admin.permissions import require_permission
from app.modules.admin.privileged_operations import (
    begin_idempotent_operation,
    canonical_payload_hash,
    complete_idempotent_operation,
    require_idempotency_key,
)

router = APIRouter(prefix="/api/admin/questions", tags=["admin"], route_class=EnvelopeAPIRoute)


class AdminQuestionResponse(BaseModel):
    id: UUID
    question_text: str
    question_category: str
    difficulty: str
    job_roles: list[str]
    technologies: list[str]
    source: str | None
    usage_count: int
    created_at: datetime
    moderation_status: str
    moderated_by: UUID | None
    moderated_at: datetime | None


class AdminQuestionListResponse(BaseModel):
    items: list[AdminQuestionResponse]
    next_cursor: str | None
    has_more: bool


class ModerateQuestionRequest(BaseModel):
    moderation_status: Literal["active", "hidden", "removed"]
    reason: str | None = Field(default=None, max_length=500)


def _to_response(question: InterviewQuestion) -> AdminQuestionResponse:
    return AdminQuestionResponse(
        id=question.id,
        question_text=question.question_text,
        question_category=question.question_category,
        difficulty=question.difficulty,
        job_roles=question.job_roles,
        technologies=question.technologies,
        source=question.source,
        usage_count=question.usage_count,
        created_at=question.created_at,
        moderation_status=question.moderation_status,
        moderated_by=question.moderated_by,
        moderated_at=question.moderated_at,
    )


async def _get_question_or_404(db: AsyncSession, question_id: UUID) -> InterviewQuestion:
    result = await db.execute(select(InterviewQuestion).where(InterviewQuestion.id == question_id))
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    return question


@router.get("", response_model=AdminQuestionListResponse)
async def list_questions(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    moderation_status: str | None = Query(default=None),
    question_category: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    _user: User = Depends(require_permission("questions", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminQuestionListResponse:
    query = select(InterviewQuestion).order_by(
        InterviewQuestion.created_at.desc(), InterviewQuestion.id.desc()
    )
    if moderation_status is not None:
        query = query.where(InterviewQuestion.moderation_status == moderation_status)
    if question_category is not None:
        query = query.where(InterviewQuestion.question_category == question_category)
    if difficulty is not None:
        query = query.where(InterviewQuestion.difficulty == difficulty)
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (InterviewQuestion.created_at < created_at)
            | (
                (InterviewQuestion.created_at == created_at)
                & (InterviewQuestion.id < UUID(entity_id))
            )
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None

    return AdminQuestionListResponse(
        items=[_to_response(r) for r in rows], next_cursor=next_cursor, has_more=has_more
    )


@router.get("/{question_id}", response_model=AdminQuestionResponse)
async def get_question(
    question_id: UUID,
    _user: User = Depends(require_permission("questions", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminQuestionResponse:
    question = await _get_question_or_404(db, question_id)
    return _to_response(question)


@router.post(
    "/{question_id}/moderate",
    response_model=AdminQuestionResponse,
    dependencies=[Depends(enforce_admin_moderation_rate_limit)],
)
async def moderate_question(
    question_id: UUID,
    payload: ModerateQuestionRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(require_permission("questions", "moderate")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminQuestionResponse:
    normalized_key = require_idempotency_key("questions.moderate", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=current_user.id,
        operation_id="questions.moderate",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash(
            {
                "question_id": question_id,
                "moderation_status": payload.moderation_status,
                "reason": payload.reason,
            }
        ),
    )
    if replay is not None:
        return AdminQuestionResponse.model_validate(replay.response_body["question"])

    question = await _get_question_or_404(db, question_id)

    before = {"moderation_status": question.moderation_status}
    question.moderation_status = payload.moderation_status
    question.moderated_by = current_user.id
    question.moderated_at = datetime.now(UTC)
    await db.flush()
    after = {"moderation_status": question.moderation_status, "reason": payload.reason}

    await record_admin_action(
        db,
        actor_user_id=current_user.id,
        action="questions.moderate",
        target_type="interview_question",
        target_id=str(question_id),
        before=before,
        after=after,
        ip_address=get_client_ip(request),
    )
    response = _to_response(question)
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=200,
            response_body={"question": response.model_dump(mode="json")},
        )
    await db.commit()
    await db.refresh(question)
    return response
