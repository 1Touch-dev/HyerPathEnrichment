"""Admin endpoints for interview-question moderation (Module 3 placeholder).

MODULE 3 PLACEHOLDER: the real interview-questions moderation feature lives on
the UNMERGED `feat/phase2-module3-interview-prep` branch, which is not present
on this branch. Migration 041 already seeded the `questions:read` /
`questions:moderate` permission rows (granted to `admin`; `questions:read`
also granted to `support`) so RBAC wiring is ready, but every route below is a
stub that only exercises the permission gate and then raises 501. This must be
revisited with a real implementation (not just permission rows) once
`feat/phase2-module3-interview-prep` merges.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.modules.admin.permissions import require_permission

router = APIRouter(prefix="/api/admin/questions", tags=["admin"], route_class=EnvelopeAPIRoute)

_NOT_IMPLEMENTED_DETAIL = (
    "Module 3 (interview questions) is not yet merged into this branch. "
    "See feat/phase2-module3-interview-prep."
)


# MODULE 3 PLACEHOLDER: list endpoint — revisit with a real implementation once
# feat/phase2-module3-interview-prep merges.
@router.get("")
async def list_questions(
    _user: User = Depends(require_permission("questions", "read")),
) -> None:
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_DETAIL)


# MODULE 3 PLACEHOLDER: detail endpoint — revisit with a real implementation
# once feat/phase2-module3-interview-prep merges.
@router.get("/{question_id}")
async def get_question(
    question_id: UUID,
    _user: User = Depends(require_permission("questions", "read")),
) -> None:
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_DETAIL)


# MODULE 3 PLACEHOLDER: moderation endpoint — revisit with a real
# implementation once feat/phase2-module3-interview-prep merges.
@router.post("/{question_id}/moderate")
async def moderate_question(
    question_id: UUID,
    _user: User = Depends(require_permission("questions", "moderate")),
) -> None:
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_DETAIL)
