from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import get_settings
from app.domain.enrichment import EnrichmentRequest
from app.enrichers.base import Enricher

logger = logging.getLogger(__name__)

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

        # Log the search parameters for debugging
        logger.info(
            f"JobSpy search: term={search_term!r}, location={location!r}, country={country!r}"
        )

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

        logger.info(
            f"JobSpy returned {len(jobs)} jobs from {len(set(j['source'] for j in jobs))} sources"
        )
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
            logger.warning("JobSpy library not installed")
            return []

        try:
            # Normalize location format for better compatibility
            # Glassdoor/Indeed prefer "City, State" or "City, Country" format
            formatted_location = self._format_location(location, country)

            # Build scrape_jobs parameters
            kwargs: dict[str, Any] = {
                "site_name": list(JOBSPY_SITES),
                "search_term": search_term,
                "results_wanted": limit,
            }

            # Add location if provided (used by LinkedIn, Indeed, Glassdoor, ZipRecruiter)
            if formatted_location:
                kwargs["location"] = formatted_location

            # Add country_indeed if provided (used by Indeed and Glassdoor for regional sites)
            # Must be lowercase country name from JobSpy's supported list
            if country:
                kwargs["country_indeed"] = country.lower()

            # Google Jobs uses google_search_term instead of search_term + location
            # Build a natural language query for Google
            if location and search_term:
                kwargs["google_search_term"] = f"{search_term} jobs in {formatted_location}"

            logger.debug(f"JobSpy kwargs: {kwargs}")

            frame = scrape_jobs(**kwargs)
        except Exception as e:
            logger.error(f"JobSpy scraping failed: {e}", exc_info=True)
            return []

        if frame is None or getattr(frame, "empty", True):
            logger.warning("JobSpy returned empty results")
            return []

        try:
            records = frame.to_dict(orient="records")
        except Exception as e:
            logger.error(f"Failed to convert JobSpy results to dict: {e}")
            return []

        if not isinstance(records, list):
            logger.warning(f"JobSpy returned non-list records: {type(records)}")
            return []

        # Filter valid job records
        valid_jobs = [row for row in records if isinstance(row, dict)]
        logger.info(
            f"JobSpy scraped {len(valid_jobs)} valid jobs from {len(records)} total records"
        )

        return valid_jobs

    def _format_location(self, location: str | None, country: str | None) -> str:
        """Format location for better job board compatibility.

        Glassdoor and Indeed work better with:
        - "City, State" (US)
        - "City, Country" (International)
        - Just "State" or "Country" also works
        """
        if not location:
            return ""

        location = location.strip()

        # If location already has a comma, use as-is
        if "," in location:
            return location

        # For US locations, try to add state/country context
        if country:
            country_name = country.upper()
            # If it's USA and location is just a city, it's ambiguous but JobSpy will try
            # For other countries, append country name for clarity
            if country_name not in ("USA", "US", "UNITED STATES"):
                # Only append if location doesn't already end with country
                if not location.lower().endswith(country.lower()):
                    return f"{location}, {country}"

        return location
