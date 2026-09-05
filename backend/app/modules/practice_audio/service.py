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


def _base_mime_type(mime_type: str) -> str:
    """Strip codec parameters for the `audio_format` column (`VARCHAR(20)`).

    Browsers' `MediaRecorder.mimeType` often includes codec info (e.g.
    Chrome's default `"audio/webm;codecs=opus"`, 23 chars) which overflows the
    column and previously crashed every audio upload with an uncaught
    `StringDataRightTruncationError` (500 INTERNAL_ERROR, no validation error
    surfaced to the user). The base MIME type ("audio/webm") is all this
    column needs to represent; the *original* string (with codecs) is still
    passed through unchanged to `AudioStorageClient.upload_audio` and
    `WhisperClient.transcribe_audio` below, since R2's `Content-Type` header
    and Whisper's multipart part both legitimately want the fully qualified
    value. The trailing `[:20]` is a defensive backstop matching the
    column's actual width in case some future MIME type's base is longer
    than every entry in `ALLOWED_AUDIO_MIME_TYPES` today (all <= 11 chars).
    """
    return mime_type.split(";")[0].strip()[:20]


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
        audio_format=_base_mime_type(audio_format),
        transcription_status="processing",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=AUDIO_RETENTION_DAYS),
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)

    logger.info(
        "Starting audio transcription",
        extra={
            "recording_id": str(recording.id),
            "practice_session_id": str(practice_session_id),
            "audio_format": audio_format,
            "file_size_bytes": file_size_bytes,
        },
    )

    try:
        client = WhisperClient(settings)
        result = await client.transcribe_audio(audio_bytes, filename, audio_format)
        recording.transcription = result.text
        recording.duration_seconds = result.duration
        recording.transcription_status = "completed"
        recording.analysis_data = asdict(analyze_transcription(result.text, result.duration))

        # Diagnostic for "transcription is garbage" reports (e.g. Whisper's
        # well-known hallucination of filler words like "you" on near-silent
        # input): a suspiciously low bytes-per-second ratio is a strong signal
        # the *recording itself* has little/no real audio signal — client mic
        # muted/wrong input device, not a transcription bug. Logged, not
        # enforced, since it's a heuristic (real quiet speech can also compress
        # well) — check `bytes_per_second` alongside `transcription_text` below
        # to tell "empty mic" apart from "genuinely short/quiet answer".
        bytes_per_second = round(file_size_bytes / result.duration, 1) if result.duration else None
        # `bytes_per_second`/`transcription_length` are safe at INFO (useful
        # for the "likely silent mic" diagnostic without exposing content);
        # `transcription_text` is the candidate's actual spoken words, so it's
        # logged separately at DEBUG only.
        logger.info(
            "Audio transcription completed",
            extra={
                "recording_id": str(recording.id),
                "transcription_length": len(result.text),
                "duration_seconds": result.duration,
                "language": result.language,
                "bytes_per_second": bytes_per_second,
                "likely_silent_input": bytes_per_second is not None and bytes_per_second < 1000,
            },
        )
        logger.debug(
            "Audio transcription text",
            extra={"recording_id": str(recording.id), "transcription_text": result.text},
        )
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
