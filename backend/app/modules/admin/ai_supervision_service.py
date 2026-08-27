"""Service layer for the AI-agent supervision (audit/oversight) view.

See task-orchestration/machine-2-parallel-tracks/04-rbac-admin-platform.md's
"AI-agent supervision (audit/oversight view)" section. This module owns both:

- the read surface (`list_ai_actions`/`get_ai_action`) the doc's own text
  describes as this chunk's responsibility, and
- a shared write helper (`record_ai_action`) added per this plan's explicit
  design decision, so later callers (recruiter_actions/outreach/resume_tailoring
  -- wired in a separate later chunk) have one canonical insert path instead of
  each hand-rolling `db.add(AiActionAuditLog(...))` differently.

Kept as its own service module rather than folded into `roles_service.py` or
`service.py`, per the doc's own file-layout note: this is a read-only
aggregation view over other modules' actions, not a role/permission mutation,
and does not share `roles_service.py`'s audit-log-every-mutation shape.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.ai_supervision_models import AiActionAuditLog
from app.modules.admin.pagination import decode_cursor, encode_cursor


async def record_ai_action(
    db: AsyncSession,
    *,
    action_type: str,
    candidate_user_id: UUID | None,
    triggered_by_user_id: UUID | None = None,
    related_id: UUID | None = None,
    summary: str | None = None,
) -> AiActionAuditLog:
    """Canonical insert path for a new `AiActionAuditLog` row. Callers (a later
    chunk wires this into `recruiter_actions.service.apply_for_candidate`'s
    autonomous branch, `workers.tasks.outreach._generate_outreach_draft_job`,
    and `workers.tasks.resume_tailoring._tailor_resume_job`) call this at the
    point their own action executes -- rows are never backfilled here."""
    record = AiActionAuditLog(
        action_type=action_type,
        candidate_user_id=candidate_user_id,
        triggered_by_user_id=triggered_by_user_id,
        related_id=related_id,
        summary=summary,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def list_ai_actions(
    db: AsyncSession,
    *,
    candidate_id: UUID | None = None,
    recruiter_id: UUID | None = None,
    action_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[AiActionAuditLog], str | None, bool]:
    """List AI-action audit rows, newest first, filterable by any combination of
    candidate/recruiter/action_type/since/until. Cursor pagination follows this
    module's existing `repository.list_audit_logs` convention (opaque
    Stripe-style cursor over `(created_at, id)`, never bare offsets)."""
    query = select(AiActionAuditLog).order_by(
        AiActionAuditLog.created_at.desc(), AiActionAuditLog.id.desc()
    )
    if candidate_id is not None:
        query = query.where(AiActionAuditLog.candidate_user_id == candidate_id)
    if recruiter_id is not None:
        query = query.where(AiActionAuditLog.triggered_by_user_id == recruiter_id)
    if action_type is not None:
        query = query.where(AiActionAuditLog.action_type == action_type)
    if since is not None:
        query = query.where(AiActionAuditLog.created_at >= since)
    if until is not None:
        query = query.where(AiActionAuditLog.created_at <= until)
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (AiActionAuditLog.created_at < created_at)
            | (
                (AiActionAuditLog.created_at == created_at)
                & (AiActionAuditLog.id < UUID(entity_id))
            )
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    return rows, next_cursor, has_more


async def get_ai_action(db: AsyncSession, action_id: UUID) -> AiActionAuditLog | None:
    result = await db.execute(select(AiActionAuditLog).where(AiActionAuditLog.id == action_id))
    return result.scalar_one_or_none()
