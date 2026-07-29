from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, List
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

    async def list(
        self, limit: int, offset: int, include_internal: bool = False
    ) -> tuple[list[JobRecord], int]:
        clamped_limit = max(1, min(limit, 100))
        clamped_offset = max(0, offset)

        # Build base query with internal filter
        base_query = select(JobRecord)
        if not include_internal:
            base_query = base_query.where(JobRecord.is_internal.is_(False))

        # Count with filter
        total_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = int(total_result.scalar_one())

        # List with filter
        statement = (
            base_query.order_by(JobRecord.created_at.desc())
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
        job.updated_at = datetime.now(UTC)
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

    async def create_child_job(
        self,
        parent_job: JobRecord,
        request: EnrichmentRequest,
        tier_assignment: List[str],
    ) -> JobRecord:
        """Create a child job linked to parent."""
        child = JobRecord(
            id=f"job_{uuid4().hex}",
            status=JobStatus.queued.value,
            request_payload=request.model_dump(mode="json"),
            dossier_payload={},
            identifier_hashes=parent_job.identifier_hashes,
            parent_job_id=parent_job.id,
            child_job_ids=[],
            tier_assignment=tier_assignment,
            is_internal=True,
        )
        self.db.add(child)

        # Update parent's child_job_ids
        if not parent_job.child_job_ids:
            parent_job.child_job_ids = []
        parent_job.child_job_ids = parent_job.child_job_ids + [child.id]

        return child

    async def get_children(self, parent_job_id: str) -> List[JobRecord]:
        """Get all child jobs for a parent."""
        statement = select(JobRecord).where(JobRecord.parent_job_id == parent_job_id)
        result = await self.db.execute(statement)
        children: List[JobRecord] = list(result.scalars().all())
        return children

    async def get_parent(self, child_job: JobRecord) -> JobRecord | None:
        """Get parent job from child."""
        if not child_job.parent_job_id:
            return None
        return await self.get(child_job.parent_job_id)

    async def all_children_complete(self, parent_job_id: str) -> bool:
        """Check if all child jobs are in terminal status."""
        children: List[JobRecord] = await self.get_children(parent_job_id)
        if not children:
            return False

        return all(JobStatus(child.status) in TERMINAL_STATUSES for child in children)
