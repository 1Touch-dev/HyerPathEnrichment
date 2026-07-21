from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.identifiers import hashes_from_request
from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import JobStatus
from app.modules.enrichment.job_events import TERMINAL_STATUSES, publish_job_status
from app.modules.enrichment.models import JobRecord


class JobRepository:
    """Single owner of enrichment job persistence."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        request: EnrichmentRequest,
        status: JobStatus,
        *,
        dossier_payload: dict[str, Any] | None = None,
    ) -> JobRecord:
        job = JobRecord(
            id=f"job_{uuid4().hex}",
            status=status.value,
            request_payload=request.model_dump(mode="json"),
            dossier_payload=dossier_payload or {},
            identifier_hashes=hashes_from_request(request),
        )
        self.db.add(job)
        return job

    async def get(self, job_id: str) -> JobRecord | None:
        return await self.db.get(JobRecord, job_id)

    async def list(self, limit: int, offset: int) -> tuple[list[JobRecord], int]:
        clamped_limit = max(1, min(limit, 100))
        clamped_offset = max(0, offset)

        total_result = await self.db.execute(select(func.count()).select_from(JobRecord))
        total = int(total_result.scalar_one())

        statement = (
            select(JobRecord)
            .order_by(JobRecord.created_at.desc())
            .limit(clamped_limit)
            .offset(clamped_offset)
        )
        result = await self.db.execute(statement)
        return list(result.scalars().all()), total

    async def mark_status(
        self,
        job: JobRecord,
        status: JobStatus,
        *,
        dossier_payload: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> JobRecord:
        job.status = status.value
        if dossier_payload is not None:
            job.dossier_payload = dossier_payload
        job.updated_at = datetime.now(timezone.utc)
        if commit:
            await self.db.commit()
            await self.db.refresh(job)
            if status in TERMINAL_STATUSES:
                await publish_job_status(job.id, status)
        return job

    async def flush(self) -> None:
        await self.db.flush()

    async def commit(self) -> None:
        await self.db.commit()

    async def refresh(self, job: JobRecord) -> JobRecord:
        await self.db.refresh(job)
        return job

    async def rollback(self) -> None:
        await self.db.rollback()
