"""Suppression list — Redis fast-path with SQL durable record."""

from __future__ import annotations

import logging

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.identifiers import hash_identifier, request_identifier_values
from app.compliance.models import SuppressionRecord
from app.domain.enrichment import EnrichmentRequest
from app.infrastructure.redis import get_redis_client

logger = logging.getLogger(__name__)

SUPPRESSION_SET_KEY = "suppression:hashes"


async def add_suppression(db: AsyncSession, identifier: str, reason: str | None = None) -> None:
    identifier_hash = hash_identifier(identifier)
    record = SuppressionRecord(identifier_hash=identifier_hash, reason=reason or "")
    await db.merge(record)
    await db.commit()
    try:
        await get_redis_client().sadd(SUPPRESSION_SET_KEY, identifier_hash)
    except RedisError:
        logger.warning("redis unavailable during add_suppression; SQL record persisted")


async def check_suppression(db: AsyncSession, identifier: str) -> bool:
    identifier_hash = hash_identifier(identifier)
    try:
        if await get_redis_client().sismember(SUPPRESSION_SET_KEY, identifier_hash):
            return True
    except RedisError:
        logger.warning("redis unavailable during check_suppression; falling back to SQL")
    statement = select(SuppressionRecord).where(SuppressionRecord.identifier_hash == identifier_hash)
    result = await db.execute(statement)
    suppressed = result.scalar_one_or_none() is not None
    if suppressed:
        try:
            await get_redis_client().sadd(SUPPRESSION_SET_KEY, identifier_hash)
        except RedisError:
            pass
    return suppressed


async def is_request_suppressed(db: AsyncSession, request: EnrichmentRequest) -> bool:
    for identifier in request_identifier_values(request):
        if await check_suppression(db, identifier):
            return True
    return False
