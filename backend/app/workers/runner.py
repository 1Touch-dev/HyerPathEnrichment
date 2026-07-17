"""Compatibility shim — enrichment execution lives in ``app.enrichers.pipeline``."""

from app.enrichers.pipeline import Pipeline

# Historical name used across tests and scripts.
PipelineOrchestrator = Pipeline

__all__ = ["Pipeline", "PipelineOrchestrator"]
