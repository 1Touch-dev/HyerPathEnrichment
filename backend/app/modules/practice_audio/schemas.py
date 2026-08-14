"""Pydantic schemas for the practice audio upload/status API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AudioUploadResponse(BaseModel):
    id: UUID
    practice_session_id: UUID
    transcription_status: str
    file_size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AudioStatusResponse(BaseModel):
    id: UUID
    transcription_status: str
    transcription: str | None
    analysis_data: dict[str, Any] | None
    voice_tone_signals: dict[str, Any] | None
    duration_seconds: float | None

    model_config = {"from_attributes": True}
