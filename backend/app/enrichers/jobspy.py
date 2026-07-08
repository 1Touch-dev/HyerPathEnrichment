from __future__ import annotations

import asyncio
from typing import Any

from app.config import get_settings
from app.enrichers.base import Enricher
from app.models import EnrichmentRequest


class JobSpyEnricher(Enricher):
    source_name = "JobSpy"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.job_search)

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        settings = get_settings()
        rows = await asyncio.to_thread(
            self._scrape,
            request.job_search or "",
            request.company,
            settings.jobspy_results_per_board,
        )
        jobs = [
            {
                "title": str(row.get("title") or request.job_search or "Unknown role"),
                "company": str(row.get("company") or request.company or "Unknown"),
                "location": str(row.get("location") or "Unknown"),
                "remote": bool(row.get("is_remote") or row.get("remote") or False),
                "source": str(row.get("site") or self.source_name),
            }
            for row in rows
        ]
        return {"jobs": jobs} if jobs else {}

    def _scrape(self, search_term: str, company: str | None, limit: int) -> list[dict[str, Any]]:
        try:
            from jobspy import scrape_jobs
        except ImportError:
            return []
        try:
            frame = scrape_jobs(
                site_name=["indeed", "linkedin"],
                search_term=search_term,
                results_wanted=limit,
            )
        except Exception:
            return []
        if frame is None or getattr(frame, "empty", True):
            return []
        return frame.to_dict(orient="records")
