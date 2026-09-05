"""Pydantic schemas for ephemeral, on-demand resume tailoring.

See task-orchestration/machine-2-parallel-tracks/10-resume-tailoring.md — this
feature has no ORM model at all (never persisted), so this file only contains
request/response shapes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TailorResumeRequest(BaseModel):
    document_id: str
    target_company: str = Field(..., min_length=1, max_length=255)
    target_role: str | None = Field(default=None, max_length=255)


class TailorResumeJobResponse(BaseModel):
    rq_job_id: str
    message: str = "Resume tailoring started"


class TailoredResumeResultResponse(BaseModel):
    status: str  # "queued" | "started" | "finished" | "failed" | "not_found"
    summary: str | None = None
    emphasized_skills: list[str] = Field(default_factory=list)
    reordered_bullets: list[str] = Field(default_factory=list)
    research_degraded: bool | None = None
