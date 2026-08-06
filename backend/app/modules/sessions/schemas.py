"""Pydantic schemas for practice sessions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class SessionCreate(BaseModel):
    """Schema for creating a new practice session."""

    session_type: str = Field(..., min_length=1, max_length=50)


class SessionProgressUpdate(BaseModel):
    """Schema for updating session progress."""

    questions_attempted: int = Field(..., ge=0)
    score: float | None = Field(None, ge=0, le=100)


class SessionComplete(BaseModel):
    """Schema for completing a session."""

    overall_score: float = Field(..., ge=0, le=100)


class SessionResponse(BaseModel):
    """Schema for session response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    session_type: str
    started_at: datetime
    completed_at: datetime | None
    status: str
    questions_attempted: int
    questions_completed: int
    overall_score: Decimal | None
    session_metadata: dict


class SessionList(BaseModel):
    """Schema for paginated session list."""

    sessions: list[SessionResponse]
    total: int
    limit: int
    offset: int


class AttemptCreate(BaseModel):
    """Schema for creating a new question attempt."""

    question_text: str = Field(
        ...,
        description="The interview question being answered",
        min_length=1,
        max_length=2000,
    )
    text_response: str = Field(
        ...,
        description="The candidate's text response",
        min_length=1,
        max_length=10000,
    )
    time_taken_seconds: int | None = Field(
        None,
        description="Time taken to answer in seconds",
        ge=0,
    )


class AttemptResponse(BaseModel):
    """Schema for question attempt response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    user_id: UUID
    response_type: str
    text_response: str | None
    ai_score: Decimal | None
    score_breakdown: dict[str, float] | None
    ai_feedback: str | None
    time_taken_seconds: int | None
    attempted_at: datetime

    # Extended feedback fields (from attempt_metadata)
    strengths: list[str] | None = None
    improvements: list[str] | None = None
    feedback_error: str | None = None

    @classmethod
    def from_orm_with_metadata(cls, attempt) -> AttemptResponse:
        """Create response from ORM model, extracting attempt_metadata fields."""
        data = {
            "id": attempt.id,
            "session_id": attempt.session_id,
            "user_id": attempt.user_id,
            "response_type": attempt.response_type,
            "text_response": attempt.text_response,
            "ai_score": attempt.ai_score,
            "score_breakdown": attempt.score_breakdown,
            "ai_feedback": attempt.ai_feedback,
            "time_taken_seconds": attempt.time_taken_seconds,
            "attempted_at": attempt.attempted_at,
        }

        # Extract from attempt_metadata if available
        if hasattr(attempt, "attempt_metadata") and isinstance(attempt.attempt_metadata, dict):
            data["strengths"] = attempt.attempt_metadata.get("strengths")
            data["improvements"] = attempt.attempt_metadata.get("improvements")
            data["feedback_error"] = attempt.attempt_metadata.get("feedback_error")

        return cls(**data)
