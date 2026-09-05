"""Pydantic schemas for session tracking API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# Request schemas
class SessionCreateRequest(BaseModel):
    """Request to create a new practice session."""

    session_type: str = Field(..., description="Type of practice session")
    session_metadata: dict[str, Any] = Field(default_factory=dict, description="Optional metadata")


class SessionUpdateRequest(BaseModel):
    """Request to update session status or metrics."""

    status: str | None = Field(None, description="New status")
    questions_attempted: int | None = Field(None, ge=0)
    questions_completed: int | None = Field(None, ge=0)
    overall_score: float | None = Field(None, ge=0, le=100)
    session_metadata: dict[str, Any] | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"pending", "in_progress", "completed", "failed", "abandoned"}
            if v not in allowed:
                raise ValueError(f"status must be one of {allowed}")
        return v


class QuestionAttemptRequest(BaseModel):
    """Request to record a question attempt."""

    question_id: UUID | None = None
    response_type: str = Field(..., description="Type of response: 'text' or 'audio'")
    text_response: str | None = None
    audio_recording_id: UUID | None = None
    ai_score: float | None = Field(None, ge=0, le=100)
    score_breakdown: dict[str, Any] | None = None
    ai_feedback: str | None = None
    time_taken_seconds: int | None = Field(None, ge=0)

    @field_validator("response_type")
    @classmethod
    def validate_response_type(cls, v: str) -> str:
        if v not in {"text", "audio"}:
            raise ValueError("response_type must be 'text' or 'audio'")
        return v


# Response schemas
class QuestionAttemptResponse(BaseModel):
    """Response for a question attempt."""

    id: UUID
    session_id: UUID
    user_id: UUID
    question_id: UUID | None
    # Denormalized from interview_questions.question_text (question_attempts.question_id's
    # FK target, migration 033) — QuestionAttempt has no declared relationship for it, so
    # this is filled in by session_manager.py's `_fetch_question_texts` (called from
    # `_serialize_session` and `add_attempt`), not by `from_attributes` reading it off the
    # ORM instance directly. None for attempts whose question was later deleted (FK is ON
    # DELETE SET NULL) or that have no question_id.
    question_text: str | None = None
    response_type: str
    text_response: str | None
    audio_recording_id: UUID | None
    ai_score: float | None
    score_breakdown: dict[str, Any] | None
    ai_feedback: str | None
    time_taken_seconds: int | None
    attempted_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    """Response for a practice session."""

    id: UUID
    user_id: UUID
    session_type: str
    started_at: datetime
    completed_at: datetime | None
    status: str
    questions_attempted: int
    questions_completed: int
    overall_score: float | None
    session_metadata: dict[str, Any]
    attempts: list[QuestionAttemptResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """Response for listing sessions."""

    sessions: list[SessionResponse]
    total: int
    limit: int
    offset: int
