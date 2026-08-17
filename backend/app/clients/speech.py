"""OpenAI Whisper speech-to-text client for audio transcription.

Handles audio file transcription using OpenAI's Whisper API with retry logic,
file size validation, and timeout management.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import Settings

logger = logging.getLogger(__name__)

MAX_AUDIO_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB
WHISPER_TIMEOUT_SECONDS = 120.0


class WhisperError(Exception):
    """Raised when Whisper API operations fail."""


@dataclass(slots=True)
class TranscriptionResult:
    """Result of audio transcription."""

    text: str
    language: str | None = None
    duration: float | None = None


def validate_audio_file_size(file_size: int) -> None:
    """Validate audio file size is within API limits.

    Args:
        file_size: Size of audio file in bytes

    Raises:
        WhisperError: If file size exceeds maximum
    """
    if file_size > MAX_AUDIO_FILE_SIZE_BYTES:
        raise WhisperError(
            f"Audio file size {file_size} bytes exceeds "
            f"maximum {MAX_AUDIO_FILE_SIZE_BYTES} bytes (25MB)"
        )


class WhisperClient:
    """OpenAI Whisper API client for audio transcription."""

    def __init__(self, settings: Settings) -> None:
        """Initialize Whisper client.

        Args:
            settings: Application settings with OpenAI API key
        """
        self._api_key = settings.openai_api_key.strip()
        if not self._api_key:
            logger.warning("OpenAI API key not configured, transcription will fail")

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def transcribe_audio(
        self,
        audio_data: bytes,
        filename: str,
        audio_format: str = "audio/mpeg",
    ) -> TranscriptionResult:
        """Transcribe audio file using Whisper API.

        Args:
            audio_data: Raw audio file bytes
            filename: Original filename (for API request)
            audio_format: Audio MIME type (default: audio/mpeg)

        Returns:
            TranscriptionResult with text and optional metadata

        Raises:
            WhisperError: If transcription fails or API returns error
        """
        if not self._api_key:
            raise WhisperError("OpenAI API key not configured")

        # Validate file size
        file_size = len(audio_data)
        validate_audio_file_size(file_size)

        try:
            async with httpx.AsyncClient(timeout=WHISPER_TIMEOUT_SECONDS) as client:
                # Prepare multipart form data
                files = {
                    "file": (filename, audio_data, audio_format),
                }
                data = {
                    "model": "whisper-1",
                    "response_format": "verbose_json",
                }
                headers = {
                    "Authorization": f"Bearer {self._api_key}",
                }

                logger.info(
                    "Calling Whisper API",
                    extra={
                        "audio_filename": filename[:32],
                        "file_size": file_size,
                        "audio_format": audio_format,
                    },
                )

                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers,
                    data=data,
                    files=files,
                )
                response.raise_for_status()

                result = response.json()
                text = result.get("text", "").strip()

                if not text:
                    raise WhisperError("Whisper API returned empty transcription")

                # `text_length` is safe at INFO; `text_preview` is the
                # candidate's actual spoken words (PII), so it's DEBUG-only.
                logger.info(
                    "Transcription successful",
                    extra={
                        "audio_filename": filename[:32],
                        "text_length": len(text),
                        "language": result.get("language"),
                        "whisper_duration": result.get("duration"),
                    },
                )
                logger.debug(
                    "Transcription text preview",
                    extra={"audio_filename": filename[:32], "text_preview": text[:200]},
                )

                return TranscriptionResult(
                    text=text,
                    language=result.get("language"),
                    duration=result.get("duration"),
                )

        except httpx.HTTPStatusError as exc:
            error_detail = exc.response.text
            logger.error(
                "Whisper API error",
                exc_info=True,
                extra={
                    "status_code": exc.response.status_code,
                    "error_detail": error_detail[:200],
                },
            )
            raise WhisperError(f"Whisper API error: {error_detail}") from exc
        except httpx.HTTPError as exc:
            logger.error("Whisper API network error", exc_info=True)
            raise WhisperError(f"Network error: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected transcription error", exc_info=True)
            raise WhisperError(f"Transcription failed: {exc}") from exc
