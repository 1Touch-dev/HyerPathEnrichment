from sqlalchemy.ext.asyncio import AsyncSession

from app.enrichers.pipeline import Pipeline
from app.modules.enrichment.service import EnrichmentService, get_enrichment_service
from app.workers.runner import PipelineOrchestrator


def get_orchestrator(db: AsyncSession) -> PipelineOrchestrator:
    """Compatibility factory — prefer EnrichmentService / Pipeline."""
    return Pipeline(db)


__all__ = ["EnrichmentService", "Pipeline", "PipelineOrchestrator", "get_enrichment_service", "get_orchestrator"]
