"""Pydantic schemas for JD-tailored interview practice (Module 4, Module E)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.questions.schemas import QuestionCategory, QuestionDifficulty


class JdPracticeRequest(BaseModel):
    job_match_id: str  # required — this endpoint only exists for a JD the candidate
    # is actually tracking (Module C), never an arbitrary pasted JD;
    # keeps scope bounded to "practice for THIS interview" per the
    # original feature request, not a general-purpose JD-paste tool
    category: QuestionCategory | None = None
    difficulty: QuestionDifficulty | None = None
    count: int = Field(default=5, ge=1, le=10)


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
    job_match_id: str
    practice_session_id: UUID  # a new PracticeSession row created with
    # session_type="jd_tailored" and session_metadata=
    # {"job_match_id": ..., "job_title": ..., "company": ...}
