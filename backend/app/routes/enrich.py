from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EnrichmentJobResponse, EnrichmentRequest, JobStatus
from app.services import get_orchestrator
from app.storage.db import get_db_session

router = APIRouter(tags=["enrichment"])


@router.post("/enrich", response_model=EnrichmentJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_enrichment_job(
    request: EnrichmentRequest,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    orchestrator = get_orchestrator(db)
    job = await orchestrator.run(request)
    return EnrichmentJobResponse(id=job.id, status=JobStatus(job.status), dossier=job.dossier_payload)


@router.get("/enrich/{job_id}", response_model=EnrichmentJobResponse)
async def get_enrichment_job(
    job_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    orchestrator = get_orchestrator(db)
    job = await orchestrator.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return EnrichmentJobResponse(id=job.id, status=JobStatus(job.status), dossier=job.dossier_payload)


@router.post("/enrich/sync", response_model=EnrichmentJobResponse)
async def create_sync_enrichment(
    request: EnrichmentRequest,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    orchestrator = get_orchestrator(db)
    job = await orchestrator.run(request)
    return EnrichmentJobResponse(id=job.id, status=JobStatus(job.status), dossier=job.dossier_payload)
