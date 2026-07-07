from sqlalchemy.ext.asyncio import AsyncSession

from app.workers.runner import PipelineOrchestrator


def get_orchestrator(db: AsyncSession) -> PipelineOrchestrator:
    return PipelineOrchestrator(db)
