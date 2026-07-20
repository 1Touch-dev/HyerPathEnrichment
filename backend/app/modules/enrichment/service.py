"""Application-level enrichment use cases — start/poll jobs; does not run enrichers."""

from __future__ import annotations

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ServiceUnavailableError
from app.domain.dossier import Dossier
from app.domain.enrichment import (
    EnrichmentJobListItem,
    EnrichmentJobListResponse,
    EnrichmentJobResponse,
    EnrichmentRequest,
)
from app.domain.enums import JobStatus
from app.enrichers.pipeline import Pipeline
from app.workers.queue import enqueue_enrichment


class EnrichmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.pipeline = Pipeline(db)

    async def enrich_async(self, request: EnrichmentRequest) -> EnrichmentJobResponse:
        if await self.pipeline.is_request_suppressed(request):
            job = await self.pipeline.create_suppressed_job(request)
            return self._to_response(job)

        job = await self.pipeline.create_queued_job(request)
        try:
            enqueue_enrichment(job.id)
        except RedisError:
            job.status = JobStatus.failed.value
            await self.db.commit()
            raise ServiceUnavailableError(
                "job queue unavailable",
                meta={"job_id": job.id},
            )
        return self._to_response(job)

    async def enrich_sync(self, request: EnrichmentRequest) -> EnrichmentJobResponse:
        job = await self.pipeline.run(request)
        return self._to_response(job)

    async def get_job(self, job_id: str) -> EnrichmentJobResponse:
        job = await self.pipeline.get_job(job_id)
        if job is None:
            raise NotFoundError("job not found", meta={"job_id": job_id})
        return self._to_response(job)

    async def list_jobs(self, limit: int, offset: int) -> EnrichmentJobListResponse:
        jobs, total = await self.pipeline.list_jobs(limit, offset)
        return EnrichmentJobListResponse(
            jobs=[
                EnrichmentJobListItem(
                    id=job.id,
                    status=JobStatus(job.status),
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                    request_payload=job.request_payload,
                    identifier_summary=Pipeline.identifier_summary_from_payload(job.request_payload),
                )
                for job in jobs
            ],
            total=total,
            limit=max(1, min(limit, 100)),
            offset=max(0, offset),
        )

    @staticmethod
    def _to_response(job) -> EnrichmentJobResponse:
        return EnrichmentJobResponse(
            id=job.id,
            status=JobStatus(job.status),
            dossier=Dossier.model_validate(job.dossier_payload or {}),
        )


def get_enrichment_service(db: AsyncSession) -> EnrichmentService:
    return EnrichmentService(db)
