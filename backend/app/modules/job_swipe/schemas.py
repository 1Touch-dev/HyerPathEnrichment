from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SwipeableMatchResponse(BaseModel):
    """One card in the swipe deck — same shape as Module 1's JobMatchResponse, re-exposed here for this UI."""

    match_id: str
    job_posting_id: str
    title: str
    company: str
    location: str | None
    remote: bool
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    overall_score: float
    explanation: str | None
    is_blurred: bool = False
    created_at: datetime
    below_similarity_threshold: bool
    source_url: str | None
    applied_at: datetime | None


class SwipeDeckResponse(BaseModel):
    cards: list[SwipeableMatchResponse]
    has_more: bool


class SwipeActionRequest(BaseModel):
    direction: Literal["right", "left", "up"]


class SwipeActionResponse(BaseModel):
    match_id: str
    direction: str
    created_at: datetime
