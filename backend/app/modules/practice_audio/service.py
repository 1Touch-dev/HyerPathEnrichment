"""Orchestrates audio upload -> R2 storage -> Whisper transcription ->
heuristic analysis for one practice audio submission.

Layer: modules/ (API-facing use case). Calls services/ + clients/ only.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.speech import WhisperClient, WhisperError
from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationAppError
from app.modules.sessions.models import PracticeAudioRecording, PracticeSession
from app.services.audio_analysis import analyze_transcription
from app.services.audio_storage import AudioStorageClient

logger = logging.getLogger(__name__)

AUDIO_RETENTION_DAYS = 7  # matches existing GDPR retention convention (audio_cleanup.py)


async def upload_and_process_audio(
    db: AsyncSession,
    user_id: UUID,
    practice_session_id: UUID,
    audio_bytes: bytes,
    filename: str,
    audio_format: str,
    settings: Settings,
) -> PracticeAudioRecording:
    """Store, transcribe, and analyze one practice audio submission."""
    session_stmt = select(PracticeSession).where(
        PracticeSession.id == practice_session_id, PracticeSession.user_id == user_id
    )
    session = (await db.execute(session_stmt)).scalar_one_or_none()
    if not session:
        raise NotFoundError(f"Practice session {practice_session_id} not found")

    max_bytes = settings.practice_audio_max_upload_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise ValidationAppError(
            f"Audio file exceeds {settings.practice_audio_max_upload_mb}MB limit"
        )

    storage_client = AudioStorageClient()
    storage_path, file_size_bytes = await storage_client.upload_audio(
        audio_bytes,
        filename,
        audio_format,
        str(user_id),
        str(practice_session_id),
    )

    recording = PracticeAudioRecording(
        id=uuid4(),
        user_id=user_id,
        practice_session_id=practice_session_id,
        storage_path=storage_path,
        file_size_bytes=file_size_bytes,
        audio_format=audio_format,
        transcription_status="processing",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=AUDIO_RETENTION_DAYS),
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)

    try:
        client = WhisperClient(settings)
        result = await client.transcribe_audio(audio_bytes, filename, audio_format)
        recording.transcription = result.text
        recording.duration_seconds = result.duration
        recording.transcription_status = "completed"
        recording.analysis_data = asdict(analyze_transcription(result.text, result.duration))
    except WhisperError as exc:
        logger.error(
            "Transcription failed for audio recording",
            exc_info=True,
            extra={"recording_id": str(recording.id), "error": str(exc)},
        )
        recording.transcription_status = "failed"

    await db.commit()
    await db.refresh(recording)
    return recording
