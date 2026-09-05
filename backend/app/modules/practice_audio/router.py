"""Thin HTTP layer for practice audio upload and status."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.core.api_route import EnvelopeAPIRoute
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_practice_audio_upload_rate_limit
from app.modules.practice_audio.schemas import AudioStatusResponse, AudioUploadResponse
from app.modules.practice_audio.service import upload_and_process_audio
from app.modules.sessions.models import PracticeAudioRecording

router = APIRouter(
    prefix="/api/practice/audio", tags=["practice-audio"], route_class=EnvelopeAPIRoute
)


@router.post(
    "",
    response_model=AudioUploadResponse,
    dependencies=[Depends(enforce_practice_audio_upload_rate_limit)],
)
async def upload_audio(
    user: VerifiedUser,
    practice_session_id: UUID = Form(...),
    audio_format: str = Form(default="audio/webm"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AudioUploadResponse:
    """Upload a practice audio recording for transcription and analysis."""
    audio_bytes = await file.read()
    recording = await upload_and_process_audio(
        db,
        user.id,
        practice_session_id,
        audio_bytes,
        file.filename or "recording.webm",
        audio_format,
        settings,
    )
    return AudioUploadResponse.model_validate(recording)


@router.get("/{recording_id}", response_model=AudioStatusResponse)
async def get_audio_status(
    recording_id: UUID,
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> AudioStatusResponse:
    """Get transcription/analysis status for a practice audio recording."""
    stmt = select(PracticeAudioRecording).where(
        PracticeAudioRecording.id == recording_id, PracticeAudioRecording.user_id == user.id
    )
    recording = (await db.execute(stmt)).scalar_one_or_none()
    if not recording:
        raise NotFoundError(f"Recording {recording_id} not found")
    return AudioStatusResponse.model_validate(recording)
