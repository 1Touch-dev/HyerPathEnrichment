"""Opt-out use case — coordinates compliance suppress + purge."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.audit import log_event
from app.compliance.identifiers import hash_identifier
from app.compliance.purge import PurgeResult, purge_identifier_data
from app.compliance.suppression import add_suppression, check_suppression
from app.domain.enums import AuditEventType
import logging

logger = logging.getLogger(__name__)


class OptOutService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, identifier: str, reason: str | None = None) -> PurgeResult:
        identifier_hash = hash_identifier(identifier)
        await add_suppression(self.db, identifier, reason)
        await log_event(self.db, AuditEventType.opt_out, identifier_hash, details={"reason": reason or ""})

        try:
            purge_result = await purge_identifier_data(self.db, identifier)
        except Exception:
            logger.warning("purge failed for identifier_hash=%s", identifier_hash[:12], exc_info=True)
            purge_result = PurgeResult()
            await self.db.commit()

        await log_event(
            self.db,
            AuditEventType.data_purged,
            identifier_hash,
            details={
                "jobs_cleared": purge_result.jobs_cleared,
                "photos_deleted": purge_result.photos_deleted,
                "r2_objects_deleted": purge_result.r2_objects_deleted,
            },
        )
        await self.db.commit()
        return purge_result

    async def is_suppressed(self, identifier: str) -> bool:
        return await check_suppression(self.db, identifier)


def get_opt_out_service(db: AsyncSession) -> OptOutService:
    return OptOutService(db)
