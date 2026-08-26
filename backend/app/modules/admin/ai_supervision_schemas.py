"""Pydantic response schemas for the AI-agent supervision (audit/oversight) endpoints.

See ai_supervision_models.py's `AiActionAuditLog` and
task-orchestration/machine-2-parallel-tracks/04-rbac-admin-platform.md's
"AI-agent supervision (audit/oversight view)" section.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AiActionAuditLogResponse(BaseModel):
    """Shared shape for both the list items and the single-record drill-down —
    the doc's scope ceiling ("a list ... and a way to drill into each one") does
    not call for a richer detail-only shape, so list and detail reuse one model."""

    id: UUID
    action_type: str
    candidate_user_id: UUID | None
    triggered_by_user_id: UUID | None
    related_id: UUID | None
    summary: str | None
    created_at: datetime


class AiActionAuditLogListResponse(BaseModel):
    items: list[AiActionAuditLogResponse]
    next_cursor: str | None
    has_more: bool
