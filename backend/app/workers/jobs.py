"""RQ-compatible entrypoint — keep dotted path ``app.workers.jobs.run_enrichment_job``."""

from app.workers.tasks.enrichment import run_enrichment_job

__all__ = ["run_enrichment_job"]
