"""Append-only compliance audit trail (no raw PII)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AuditEventType
from app.compliance.models import AuditLog

logger = logging.getLogger(__name__)


async def log_event(
    db: AsyncSession,
    event_type: AuditEventType,
    identifier_hash: str,
    *,
    job_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Persist one compliance event. Callers must pass a hash, never a raw identifier."""
    record = AuditLog(
        id=f"audit_{uuid4().hex}",
        event_type=event_type.value,
        identifier_hash=identifier_hash,
        job_id=job_id,
        details=details or {},
    )
    db.add(record)
    await db.flush()
    logger.info(
        "compliance audit event=%s identifier_hash=%s job_id=%s",
        event_type.value,
        identifier_hash[:12],
        job_id,
    )
    return record
