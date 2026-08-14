"""Pydantic schemas for the question bank / personalized generation API."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

JobRole = Literal["software_engineer", "data_scientist", "product_manager", "devops_engineer"]
QuestionCategory = Literal["behavioral", "technical", "system_design"]
QuestionDifficulty = Literal["easy", "medium", "hard"]


class QuestionRequest(BaseModel):
    """Query params for GET /api/questions, validated as a body for POST-style filtering."""

    job_role: JobRole
    category: QuestionCategory | None = None
    difficulty: QuestionDifficulty | None = None
    count: int = Field(default=5, ge=1, le=10)
    personalize: bool = Field(
        default=False,
        description="If true, read the candidate's most recent processed CandidateDocument "
        "and bias generation toward its skills/role (§3 Decision 1). No-op if the "
        "candidate has no processed document — falls back to the shared question bank.",
    )


class QuestionItem(BaseModel):
    """A single question returned to the client."""

    id: UUID
    question_text: str
    category: QuestionCategory
    difficulty: QuestionDifficulty
    job_roles: list[str]
    technologies: list[str]
    is_personalized: bool

    model_config = {"from_attributes": True}


class QuestionListResponse(BaseModel):
    questions: list[QuestionItem]
    source: Literal["question_bank", "generated", "mixed"]
