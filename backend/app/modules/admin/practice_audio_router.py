"""Admin practice-audio moderation endpoints (Admin Module Phase 2 —
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
from app.modules.admin.audit import record_admin_action
from app.modules.admin.pagination import decode_cursor, encode_cursor
from app.modules.admin.permissions import require_permission
from app.modules.admin.privileged_operations import (
    begin_idempotent_operation,
    canonical_payload_hash,
    complete_idempotent_operation,
    require_idempotency_key,
)
from app.modules.sessions.models import PracticeAudioRecording

router = APIRouter(prefix="/api/admin/practice-audio", tags=["admin"], route_class=EnvelopeAPIRoute)


class AdminPracticeAudioResponse(BaseModel):
    id: UUID
    user_id: UUID
    practice_session_id: UUID
    storage_path: str
    file_size_bytes: int
    duration_seconds: float | None
    audio_format: str
    transcription: str | None
    transcription_status: str
    created_at: datetime
    expires_at: datetime | None
    moderation_status: str
    moderated_by: UUID | None
    moderated_at: datetime | None


class AdminPracticeAudioListResponse(BaseModel):
    items: list[AdminPracticeAudioResponse]
    next_cursor: str | None
    has_more: bool


class ModeratePracticeAudioRequest(BaseModel):
    moderation_status: Literal["active", "hidden", "removed"]
    reason: str | None = Field(default=None, max_length=500)


def _to_response(recording: PracticeAudioRecording) -> AdminPracticeAudioResponse:
    return AdminPracticeAudioResponse(
        id=recording.id,
        user_id=recording.user_id,
        practice_session_id=recording.practice_session_id,
        storage_path=recording.storage_path,
        file_size_bytes=recording.file_size_bytes,
        duration_seconds=(
            float(recording.duration_seconds) if recording.duration_seconds is not None else None
        ),
        audio_format=recording.audio_format,
        transcription=recording.transcription,
        transcription_status=recording.transcription_status,
        created_at=recording.created_at,
        expires_at=recording.expires_at,
        moderation_status=recording.moderation_status,
        moderated_by=recording.moderated_by,
        moderated_at=recording.moderated_at,
    )


async def _get_recording_or_404(db: AsyncSession, recording_id: UUID) -> PracticeAudioRecording:
    result = await db.execute(
        select(PracticeAudioRecording).where(PracticeAudioRecording.id == recording_id)
    )
    recording = result.scalar_one_or_none()
    if recording is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Practice audio recording not found")
    return recording


@router.get("", response_model=AdminPracticeAudioListResponse)
async def list_practice_audio(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    moderation_status: str | None = Query(default=None),
    transcription_status: str | None = Query(default=None),
    _user: User = Depends(require_permission("practice_audio", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminPracticeAudioListResponse:
    query = select(PracticeAudioRecording).order_by(
        PracticeAudioRecording.created_at.desc(), PracticeAudioRecording.id.desc()
    )
    if moderation_status is not None:
        query = query.where(PracticeAudioRecording.moderation_status == moderation_status)
    if transcription_status is not None:
        query = query.where(PracticeAudioRecording.transcription_status == transcription_status)
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (PracticeAudioRecording.created_at < created_at)
            | (
                (PracticeAudioRecording.created_at == created_at)
                & (PracticeAudioRecording.id < UUID(entity_id))
            )
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None

    return AdminPracticeAudioListResponse(
        items=[_to_response(r) for r in rows], next_cursor=next_cursor, has_more=has_more
    )


@router.get("/{recording_id}", response_model=AdminPracticeAudioResponse)
async def get_practice_audio(
    recording_id: UUID,
    _user: User = Depends(require_permission("practice_audio", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminPracticeAudioResponse:
    recording = await _get_recording_or_404(db, recording_id)
    return _to_response(recording)


@router.post(
    "/{recording_id}/moderate",
    response_model=AdminPracticeAudioResponse,
    dependencies=[Depends(enforce_admin_moderation_rate_limit)],
)
async def moderate_practice_audio(
    recording_id: UUID,
    payload: ModeratePracticeAudioRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(require_permission("practice_audio", "moderate")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminPracticeAudioResponse:
    normalized_key = require_idempotency_key("practice_audio.moderate", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=current_user.id,
        operation_id="practice_audio.moderate",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash(
            {
                "recording_id": recording_id,
                "moderation_status": payload.moderation_status,
                "reason": payload.reason,
            }
        ),
    )
    if replay is not None:
        return AdminPracticeAudioResponse.model_validate(replay.response_body["recording"])

    recording = await _get_recording_or_404(db, recording_id)

    before = {"moderation_status": recording.moderation_status}
    recording.moderation_status = payload.moderation_status
    recording.moderated_by = current_user.id
    recording.moderated_at = datetime.now(UTC)
    await db.flush()
    after = {"moderation_status": recording.moderation_status, "reason": payload.reason}

    await record_admin_action(
        db,
        actor_user_id=current_user.id,
        action="practice_audio.moderate",
        target_type="practice_audio_recording",
        target_id=str(recording_id),
        before=before,
        after=after,
        ip_address=get_client_ip(request),
    )
    response = _to_response(recording)
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=200,
            response_body={"recording": response.model_dump(mode="json")},
        )
    await db.commit()
    await db.refresh(recording)
    return response
