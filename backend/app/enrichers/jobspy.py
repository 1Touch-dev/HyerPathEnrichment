from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.domain.enrichment import EnrichmentRequest
from app.enrichers.base import Enricher

# JobSpy scrapes these concurrently (ThreadPoolExecutor). Exact site strings from python-jobspy.
JOBSPY_SITES = ("linkedin", "indeed", "glassdoor", "google", "zip_recruiter")


class JobSpyEnricher(Enricher):
    source_name = "JobSpy"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.job_search)

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        settings = get_settings()

        # Build search term from job_title and job_search
        search_term = request.job_title or request.job_search or ""

        # Extract location and country for filtering
        location = request.job_location
        country = request.job_country

        rows = await asyncio.to_thread(
            self._scrape,
            search_term,
            location,
            country,
            request.company,
            settings.jobspy_results_per_board,
        )
        jobs = [
            {
                "title": str(row.get("title") or search_term or "Unknown role"),
                "company": str(row.get("company") or request.company or "Unknown"),
                "location": str(row.get("location") or location or "Unknown"),
                "remote": bool(row.get("is_remote") or row.get("remote") or False),
                "source": str(row.get("site") or self.source_name),
            }
            for row in rows
        ]
        return {"jobs": jobs} if jobs else {}

    def _scrape(
        self,
        search_term: str,
        location: str | None,
        country: str | None,
        company: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        try:
            from jobspy import scrape_jobs
        except ImportError:
            return []
        try:
            # Build scrape_jobs parameters
            kwargs: dict[str, Any] = {
                "site_name": list(JOBSPY_SITES),
                "search_term": search_term,
                "results_wanted": limit,
            }

            # Add location if provided
            if location:
                kwargs["location"] = location

            # Add country_indeed if provided (used by Indeed and Glassdoor)
            # Defaults to None which lets JobSpy use its default behavior
            if country:
                kwargs["country_indeed"] = country.lower()

            frame = scrape_jobs(**kwargs)
        except Exception:
            return []
        if frame is None or getattr(frame, "empty", True):
            return []
        records = frame.to_dict(orient="records")
        if not isinstance(records, list):
            return []
        return [row for row in records if isinstance(row, dict)]
