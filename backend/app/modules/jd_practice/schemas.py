"""Pydantic schemas for JD-tailored interview practice (Module 4, Module E)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.questions.schemas import QuestionCategory, QuestionDifficulty


class JdPracticeRequest(BaseModel):
    """Generate JD-tailored questions from a tracked match XOR a pasted JD.

    Exactly one of ``job_match_id`` or ``job_description`` must be set
    (ADR 0018). Optional ``document_id`` selects which résumé to personalize from.
    """

    job_match_id: str | None = None
    job_description: str | None = Field(default=None, min_length=50, max_length=20_000)
    job_title: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    category: QuestionCategory | None = None
    difficulty: QuestionDifficulty | None = None
    count: int = Field(default=5, ge=5, le=15)
    document_id: UUID | None = None

    @model_validator(mode="after")
    def exactly_one_jd_source(self) -> JdPracticeRequest:
        has_match = bool(self.job_match_id and self.job_match_id.strip())
        has_paste = bool(self.job_description and self.job_description.strip())
        if has_match == has_paste:
            raise ValueError("Provide exactly one of job_match_id or job_description")
        return self


class JdPracticeQuestionItem(BaseModel):
    id: UUID
    question_text: str
    category: QuestionCategory
    difficulty: QuestionDifficulty
    sample_answer: str  # exposed here (unlike questions/schemas.py's QuestionItem,
    # which omits sample_answer from the list response) since
    # this is consumed by a single "prep for my interview" flow
    # where showing the model answer after attempting is part of
    # the UX (§9.6) — this field is returned but the frontend must
    # not render it until after the candidate submits an attempt
    # (UI-layer discipline, not a schema-layer omission, since
    # JD-tailored questions aren't reused across users the way bank
    # questions are — there's no "spoiling the bank" concern, but
    # there IS a "don't let the candidate read the answer before
    # trying" UX concern, which belongs in the frontend, not the API).


class JdPracticeResponse(BaseModel):
    questions: list[JdPracticeQuestionItem]
    job_match_id: str | None  # null when questions were generated from a pasted JD
    practice_session_id: UUID  # a new PracticeSession row created with
    # session_type="jd_tailored" and session_metadata=
    # {"job_match_id": ...} or {"source": "pasted_jd", ...}
