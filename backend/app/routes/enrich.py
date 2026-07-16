from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Dossier,
    EnrichmentJobListItem,
    EnrichmentJobListResponse,
    EnrichmentJobResponse,
    EnrichmentRequest,
    JobStatus,
)
from app.routes.rate_limit import enforce_async_rate_limit, enforce_sync_rate_limit
from app.services import get_orchestrator
from app.storage.db import get_db_session
from app.workers.queue import enqueue_enrichment

router = APIRouter(tags=["enrichment"])


@router.post(
    "/enrich",
    response_model=EnrichmentJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(enforce_async_rate_limit)],
)
async def create_enrichment_job(
    request: EnrichmentRequest,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    orchestrator = get_orchestrator(db)

    if await orchestrator.is_request_suppressed(request):
        job = await orchestrator.create_suppressed_job(request)
        return EnrichmentJobResponse(
            id=job.id,
            status=JobStatus(job.status),
            dossier=Dossier.model_validate(job.dossier_payload),
        )

    job = await orchestrator.create_queued_job(request)
    try:
        enqueue_enrichment(job.id)
    except RedisError:
        job.status = JobStatus.failed.value
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="job queue unavailable",
        )
    return EnrichmentJobResponse(
        id=job.id,
        status=JobStatus(job.status),
        dossier=Dossier.model_validate(job.dossier_payload),
    )


@router.get("/enrich", response_model=EnrichmentJobListResponse)
async def list_enrichment_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobListResponse:
    orchestrator = get_orchestrator(db)
    jobs, total = await orchestrator.list_jobs(limit, offset)
    return EnrichmentJobListResponse(
        jobs=[
            EnrichmentJobListItem(
                id=job.id,
                status=JobStatus(job.status),
                created_at=job.created_at,
                updated_at=job.updated_at,
                request_payload=job.request_payload,
                identifier_summary=orchestrator.identifier_summary_from_payload(job.request_payload),
            )
            for job in jobs
        ],
        total=total,
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
    )


@router.get("/enrich/{job_id}", response_model=EnrichmentJobResponse)
async def get_enrichment_job(
    job_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    orchestrator = get_orchestrator(db)
    job = await orchestrator.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return EnrichmentJobResponse(
        id=job.id,
        status=JobStatus(job.status),
        dossier=Dossier.model_validate(job.dossier_payload),
    )


@router.post(
    "/enrich/sync",
    response_model=EnrichmentJobResponse,
    dependencies=[Depends(enforce_sync_rate_limit)],
)
async def create_sync_enrichment(
    request: EnrichmentRequest,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    orchestrator = get_orchestrator(db)
    job = await orchestrator.run(request)
    return EnrichmentJobResponse(
        id=job.id,
        status=JobStatus(job.status),
        dossier=Dossier.model_validate(job.dossier_payload),
    )
