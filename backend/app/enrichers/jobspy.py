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

        # Try LLM optimization first if enabled
        optimized_queries = None
        if settings.llm_mode.strip().lower() == "litellm":
            try:
                from app.clients.llm import litellm_optimize_job_query

                optimized_queries = await litellm_optimize_job_query(
                    search_term, location, country, settings
                )
                if optimized_queries:
                    logger.info("Using LLM-optimized job queries")
                else:
                    logger.info("LLM optimization failed, using manual query logic")
            except Exception as e:
                logger.warning(f"LLM optimization error: {e}, falling back to manual logic")
                optimized_queries = None

        rows = await asyncio.to_thread(
            self._scrape,
            search_term,
            location,
            country,
            request.company,
            settings.jobspy_results_per_board,
            optimized_queries,
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
            f"JobSpy returned {len(jobs)} jobs from {len({j['source'] for j in jobs})} sources"
        )
        return {"jobs": jobs} if jobs else {}

    def _scrape(
        self,
        search_term: str,
        location: str | None,
        country: str | None,
        company: str | None,
        limit: int,
        optimized_queries: dict[str, dict[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            from jobspy import scrape_jobs
        except ImportError:
            logger.warning("JobSpy library not installed")
            return []

        try:
            if optimized_queries:
                # Use LLM-optimized queries - call each board separately
                logger.info("Calling JobSpy separately per board with optimized queries")
                all_jobs = self._scrape_per_board(
                    scrape_jobs, optimized_queries, search_term, limit
                )
                return all_jobs
            else:
                # Fall back to manual query logic - single call for all boards
                logger.info("Building JobSpy kwargs with manual logic")
                kwargs = self._build_kwargs_manual(search_term, location, country, limit)
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

    def _build_kwargs_manual(
        self,
        search_term: str,
        location: str | None,
        country: str | None,
        limit: int,
    ) -> dict[str, Any]:
        """Build JobSpy kwargs using manual logic (fallback when LLM is disabled/fails)."""
        # Normalize location format for better compatibility
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
        if country:
            kwargs["country_indeed"] = country.lower()

        # Google Jobs uses google_search_term instead of search_term + location
        if location and search_term:
            kwargs["google_search_term"] = f"{search_term} jobs in {formatted_location}"

        return kwargs

    def _scrape_per_board(
        self,
        scrape_jobs_func: Any,
        optimized_queries: dict[str, dict[str, str]],
        fallback_search_term: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Call JobSpy separately for each board with board-specific parameters.

        This allows us to use different location formats per board (e.g., Glassdoor needs
        "City, State" while LinkedIn can handle "City, State, Country").
        """
        # Log the raw LLM-generated queries for debugging
        logger.info(
            f"LLM-generated queries: {optimized_queries}",
            extra={"llm_queries": optimized_queries},
        )

        all_jobs = []
        boards_scraped = []

        # Map of board names to their JobSpy site_name identifiers
        board_mapping = {
            "linkedin": "linkedin",
            "indeed": "indeed",
            "glassdoor": "glassdoor",
            "google": "google",
            "zip_recruiter": "zip_recruiter",
        }

        for board_key, site_name in board_mapping.items():
            board_query = optimized_queries.get(board_key, {})
            if not board_query:
                logger.warning(f"No LLM query for board: {board_key}, skipping")
                continue

            # Build kwargs for this specific board
            kwargs: dict[str, Any] = {
                "site_name": [site_name],
                "results_wanted": limit,
            }

            # Add search term
            kwargs["search_term"] = board_query.get("search_term", fallback_search_term)

            # Add location if present
            if "location" in board_query:
                kwargs["location"] = board_query["location"]

            # Add board-specific parameters
            if board_key == "indeed" and "country_indeed" in board_query:
                kwargs["country_indeed"] = board_query["country_indeed"]

            if board_key == "google" and "google_search_term" in board_query:
                kwargs["google_search_term"] = board_query["google_search_term"]
                # Google doesn't need regular location when using google_search_term
                kwargs.pop("location", None)

            logger.info(
                f"Scraping {board_key} with params: {kwargs}",
                extra={"board": board_key, "kwargs": kwargs},
            )

            try:
                frame = scrape_jobs_func(**kwargs)

                if frame is not None and not getattr(frame, "empty", True):
                    records = frame.to_dict(orient="records")
                    valid_jobs = [row for row in records if isinstance(row, dict)]
                    all_jobs.extend(valid_jobs)
                    boards_scraped.append(board_key)
                    logger.info(
                        f"{board_key}: scraped {len(valid_jobs)} jobs",
                        extra={"board": board_key, "job_count": len(valid_jobs)},
                    )
                else:
                    logger.warning(f"{board_key}: returned empty results")

            except Exception as e:
                logger.error(
                    f"{board_key}: scraping failed - {e}",
                    extra={"board": board_key, "error": str(e)},
                    exc_info=True,
                )

        logger.info(
            f"JobSpy scraped {len(all_jobs)} total jobs from {len(boards_scraped)} boards: {boards_scraped}"
        )

        return all_jobs
