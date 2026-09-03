"""Persistence helpers for privileged-operation idempotency."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import PrivilegedIdempotencyRecord

IDEMPOTENCY_RETENTION = timedelta(hours=24)


async def get_idempotency_record(
    db: AsyncSession,
    *,
    caller_user_id: UUID,
    operation: str,
    idempotency_key: str,
) -> PrivilegedIdempotencyRecord | None:
    result = await db.execute(
        select(PrivilegedIdempotencyRecord).where(
            PrivilegedIdempotencyRecord.caller_user_id == caller_user_id,
            PrivilegedIdempotencyRecord.operation == operation,
            PrivilegedIdempotencyRecord.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def create_idempotency_record(
    db: AsyncSession,
    *,
    caller_user_id: UUID,
    operation: str,
    idempotency_key: str,
    request_hash: str,
    request_id: str,
) -> PrivilegedIdempotencyRecord:
    now = datetime.now(UTC)
    record = PrivilegedIdempotencyRecord(
        id=uuid4(),
        caller_user_id=caller_user_id,
        operation=operation,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        request_id=request_id,
        created_at=now,
        expires_at=now + IDEMPOTENCY_RETENTION,
    )
    db.add(record)
    await db.flush()
    return record


async def complete_idempotency_record(
    db: AsyncSession,
    record: PrivilegedIdempotencyRecord,
    *,
    response_status: int,
    response_body: dict[str, object],
) -> None:
    record.response_status = response_status
    record.response_body = response_body
    record.completed_at = datetime.now(UTC)
    await db.flush()
