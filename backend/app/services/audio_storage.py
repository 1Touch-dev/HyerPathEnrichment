"""Audio storage service for practice audio recordings.

Handles file uploads to R2 or local cache with validation and metadata tracking.
Reuses R2StorageClient pattern for consistent storage behavior.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from app.storage.r2 import R2StorageClient

logger = logging.getLogger(__name__)

MAX_AUDIO_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB
ALLOWED_AUDIO_MIME_TYPES = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
}


class AudioStorageError(Exception):
    """Raised when audio storage operations fail."""


def validate_audio_file_size(file_size: int) -> None:
    """Validate audio file size is within acceptable limits."""
    if file_size > MAX_AUDIO_FILE_SIZE_BYTES:
        raise AudioStorageError(
            f"Audio file size {file_size} bytes exceeds "
            f"maximum {MAX_AUDIO_FILE_SIZE_BYTES} bytes (25MB)"
        )


def validate_audio_mime_type(mime_type: str) -> str:
    """Validate audio MIME type and return file extension."""
    normalized = mime_type.split(";")[0].strip().lower()
    if normalized not in ALLOWED_AUDIO_MIME_TYPES:
        raise AudioStorageError(
            f"Unsupported audio format: {normalized}. "
            f"Allowed: {', '.join(ALLOWED_AUDIO_MIME_TYPES.keys())}"
        )
    return ALLOWED_AUDIO_MIME_TYPES[normalized]


def generate_audio_storage_key(user_id: str, session_id: str, extension: str) -> str:
    """Generate unique storage key for audio recording."""
    recording_id = uuid4().hex[:12]
    return f"practice-audio/{user_id}/{session_id}/{recording_id}.{extension}"


class AudioStorageClient:
    """Upload and manage practice audio recordings with security validation."""

    def __init__(self) -> None:
        self._storage = R2StorageClient()

    async def upload_audio(
        self,
        audio_data: bytes,
        original_filename: str,
        mime_type: str,
        user_id: str,
        session_id: str,
    ) -> tuple[str, int]:
        """Upload audio recording to storage with validation.

        Args:
            audio_data: Raw audio file bytes
            original_filename: Original filename from upload
            mime_type: MIME type from upload
            user_id: User ID uploading the audio
            session_id: Practice session ID

        Returns:
            Tuple of (storage_path, file_size_bytes)

        Raises:
            AudioStorageError: If validation fails or upload fails
        """
        # Security validation
        file_size = len(audio_data)
        validate_audio_file_size(file_size)
        extension = validate_audio_mime_type(mime_type)

        # Check for corrupted files (basic validation)
        if file_size < 100:
            raise AudioStorageError("Audio file appears to be corrupted or empty")

        # Generate storage key and upload
        storage_key = generate_audio_storage_key(user_id, session_id, extension)

        try:
            await self._storage.upload_bytes(
                storage_key,
                audio_data,
                content_type=mime_type,
            )
            logger.info(
                "Uploaded audio recording",
                extra={
                    "user_id": user_id[:8],
                    "session_id": session_id[:8],
                    "file_size": file_size,
                    "storage_key": storage_key,
                },
            )
            return storage_key, file_size
        except Exception as exc:
            logger.error(
                "Failed to upload audio recording",
                exc_info=True,
                extra={
                    "user_id": user_id[:8],
                    "session_id": session_id[:8],
                    "error": str(exc),
                },
            )
            raise AudioStorageError(f"Upload failed: {exc}") from exc

    async def delete_audio(self, storage_path: str) -> bool:
        """Delete audio recording from storage.

        Args:
            storage_path: Storage path/key from upload

        Returns:
            True if deleted, False if not found
        """
        try:
            return await self._storage.delete_object(storage_path)
        except Exception as exc:
            logger.warning(
                "Failed to delete audio recording",
                exc_info=True,
                extra={"storage_path": storage_path[:32], "error": str(exc)},
            )
            return False
