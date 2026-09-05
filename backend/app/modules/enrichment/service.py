"""Application-level enrichment use cases — start/poll jobs; does not run enrichers."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ServiceUnavailableError
from app.domain.dossier import Dossier
from app.domain.enrichment import (
    EnrichmentJobListItem,
    EnrichmentJobListResponse,
    EnrichmentJobResponse,
    EnrichmentRequest,
)
from app.domain.enums import JobStatus, RequestedTier
from app.enrichers.pipeline import Pipeline
from app.modules.enrichment.models import JobRecord
from app.workers.queue import enqueue_enrichment, should_split_into_children

logger = logging.getLogger(__name__)


class EnrichmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.pipeline = Pipeline(db)

    async def enrich_async(
        self, request: EnrichmentRequest, user_id: UUID | None = None
    ) -> EnrichmentJobResponse:
        if await self.pipeline.is_request_suppressed(request):
            job = await self.pipeline.create_suppressed_job(request, user_id=user_id)
            return self._to_response(job)

        # Check if we need to split into parent-child jobs
        tiers = request.requested_tiers or []
        if should_split_into_children(tiers):
            # Create parent job
            parent_job = await self.pipeline.create_parent_job(request, user_id=user_id)

            try:
                # Create and enqueue tier1 child
                tier1_child = await self.pipeline.create_child_job(
                    parent_job, request, [RequestedTier.tier1.value]
                )
                enqueue_enrichment(tier1_child.id, [RequestedTier.tier1], is_child_job=True)

                # Create and enqueue tier234 child
                tier234_tiers: list[RequestedTier] = [
                    t
                    for t in tiers
                    if t in {RequestedTier.tier2, RequestedTier.tier3, RequestedTier.tier4}
                ]
                tier234_child = await self.pipeline.create_child_job(
                    parent_job, request, [t.value for t in tier234_tiers]
                )
                enqueue_enrichment(tier234_child.id, tier234_tiers, is_child_job=True)

                await self.db.commit()
            except Exception as e:
                # Catch ALL exceptions during enqueue (not just RedisError)
                # This includes ConnectionError, socket.timeout, OSError, etc.
                logger.error(
                    "Failed to enqueue child jobs",
                    extra={
                        "parent_job_id": parent_job.id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                parent_job.status = JobStatus.failed.value
                await self.db.commit()
                raise ServiceUnavailableError(
                    "job queue unavailable",
                    meta={"job_id": parent_job.id, "error": str(e)},
                )

            return self._to_response(parent_job)
        else:
            # Single worker path (backward compat)
            job = await self.pipeline.create_queued_job(request, user_id=user_id)
            try:
                enqueue_enrichment(job.id, request.requested_tiers)
            except Exception as e:
                # Catch ALL exceptions during enqueue
                logger.error(
                    "Failed to enqueue job",
                    extra={
                        "job_id": job.id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                job.status = JobStatus.failed.value
                await self.db.commit()
                raise ServiceUnavailableError(
                    "job queue unavailable",
                    meta={"job_id": job.id, "error": str(e)},
                )
            return self._to_response(job)

    async def enrich_sync(
        self, request: EnrichmentRequest, user_id: UUID | None = None
    ) -> EnrichmentJobResponse:
        job = await self.pipeline.run(request, user_id=user_id)
        return self._to_response(job)

    async def get_job(self, job_id: str, user_id: UUID | None = None) -> EnrichmentJobResponse:
        job = await self.pipeline.get_job(job_id)
        if job is None:
            raise NotFoundError("job not found", meta={"job_id": job_id})

        # Verify ownership if user_id provided
        if user_id is not None and job.user_id != user_id:
            raise NotFoundError("job not found", meta={"job_id": job_id})

        # Auto-redirect to parent if this is a child job
        if job.parent_job_id:
            parent = await self.pipeline.get_job(job.parent_job_id)
            if parent:
                # Verify parent ownership too
                if user_id is not None and parent.user_id != user_id:
                    raise NotFoundError("job not found", meta={"job_id": job_id})
                job = parent

        return self._to_response(job)

    async def get_job_status(self, job_id: str, user_id: UUID | None = None) -> JobStatus:
        """Quick status read used to seed the SSE stream before subscribing."""
        job = await self.pipeline.get_job(job_id)
        if job is None:
            raise NotFoundError("job not found", meta={"job_id": job_id})

        # Verify ownership if user_id provided
        if user_id is not None and job.user_id != user_id:
            raise NotFoundError("job not found", meta={"job_id": job_id})

        return JobStatus(job.status)

    async def list_jobs(
        self, limit: int, offset: int, user_id: UUID | None = None
    ) -> EnrichmentJobListResponse:
        jobs, total = await self.pipeline.list_jobs(limit, offset, user_id=user_id)
        return EnrichmentJobListResponse(
            jobs=[
                EnrichmentJobListItem(
                    id=job.id,
                    status=JobStatus(job.status),
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                    request_payload=job.request_payload,
                    identifier_summary=Pipeline.identifier_summary_from_payload(
                        job.request_payload
                    ),
                )
                for job in jobs
            ],
            total=total,
            limit=max(1, min(limit, 100)),
            offset=max(0, offset),
        )

    @staticmethod
    def _to_response(job: JobRecord) -> EnrichmentJobResponse:
        return EnrichmentJobResponse(
            id=job.id,
            status=JobStatus(job.status),
            created_at=job.created_at,
            updated_at=job.updated_at,
            dossier=Dossier.model_validate(job.dossier_payload or {}),
        )


def get_enrichment_service(db: AsyncSession) -> EnrichmentService:
    return EnrichmentService(db)
