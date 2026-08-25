from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.domain.enrichment import EnrichmentRequest
from app.enrichers.base import Enricher

logger = logging.getLogger(__name__)

# JobSpy scrapes these concurrently (ThreadPoolExecutor). Exact site strings from python-jobspy.
JOBSPY_SITES = ("linkedin", "indeed", "glassdoor", "google", "zip_recruiter")

# _normalize_publisher() below emits exactly these 6 literal strings, never anything else.
# This is a closed vocabulary agreed by convention (not shared code) with app/enrichers/merge.py,
# which independently hardcodes its own literal filter set — do NOT add an import between this
# module and merge.py for this purpose, and do NOT export a shared constant here. Keeping the
# vocabulary closed (rather than one bespoke slug per unrecognized publisher) bounds Prometheus
# metric label cardinality and job-posting dedup-key cardinality.
_NORMALIZED_PUBLISHER_VOCAB = frozenset(
    {"linkedin", "indeed", "glassdoor", "zip_recruiter", "google", "jsearch_other"}
)

# Substring aliases checked against the lowercased, stripped publisher string.
_PUBLISHER_ALIASES: tuple[tuple[str, str], ...] = (
    ("linkedin", "linkedin"),
    ("indeed", "indeed"),
    ("glassdoor", "glassdoor"),
    ("zip recruiter", "zip_recruiter"),
    ("ziprecruiter", "zip_recruiter"),
    ("zip_recruiter", "zip_recruiter"),
    ("google", "google"),
)

# JSearch's "country" query param requires an ISO 3166-1 alpha-2 code (e.g. "de"),
# unlike JobSpy's country_indeed which took free-text country names. request.job_country
# is a free-text field (frontend placeholder: "e.g., USA, Germany, Canada"), so full
# names must be mapped down before hitting the API — sending "germany" verbatim is
# accepted (HTTP 200) but silently returns zero jobs instead of erroring.
_COUNTRY_NAME_TO_ISO2: dict[str, str] = {
    "usa": "us",
    "united states": "us",
    "united states of america": "us",
    "america": "us",
    "uk": "gb",
    "united kingdom": "gb",
    "great britain": "gb",
    "england": "gb",
    "germany": "de",
    "deutschland": "de",
    "france": "fr",
    "spain": "es",
    "italy": "it",
    "netherlands": "nl",
    "the netherlands": "nl",
    "holland": "nl",
    "belgium": "be",
    "switzerland": "ch",
    "austria": "at",
    "sweden": "se",
    "norway": "no",
    "denmark": "dk",
    "finland": "fi",
    "poland": "pl",
    "portugal": "pt",
    "ireland": "ie",
    "canada": "ca",
    "mexico": "mx",
    "brazil": "br",
    "india": "in",
    "china": "cn",
    "japan": "jp",
    "south korea": "kr",
    "korea": "kr",
    "singapore": "sg",
    "australia": "au",
    "new zealand": "nz",
    "united arab emirates": "ae",
    "uae": "ae",
    "south africa": "za",
    # Middle East entries genuinely missing as of the 2026-08-22 snapshot (only
    # UAE existed before) — added for demand_intelligence's India/Middle East
    # resolution coverage requirement (machine-2-parallel-tracks/02).
    "saudi arabia": "sa",
    "qatar": "qa",
    "israel": "il",
    "egypt": "eg",
}

# JSearch defaults to the primary language of the "country" param when "language"
# is omitted, but that default is not always correct for a country whose
# JSearch-indexed postings are predominantly in a different language than its
# broader population's primary language (e.g. India: en, not one of its many
# regional languages) — see the language map below and _language_for_country().
_COUNTRY_ISO2_TO_LANGUAGE: dict[str, str] = {
    "in": "en",  # India: JSearch-indexed postings are predominantly English.
    "ae": "en",  # UAE: business/tech postings are predominantly English.
    "sa": "en",  # Saudi Arabia: same rationale as UAE.
    "qa": "en",
    "il": "en",
}


def country_to_iso2(country: str | None) -> str:
    """Best-effort mapping of a free-text country name to an ISO alpha-2 code for JSearch.

    Falls back to "us" (JSearch's own documented default) for unrecognized input rather
    than forwarding an unusable value that would silently zero out the search.
    """
    if not country or not country.strip():
        return "us"

    normalized = country.strip().lower()
    mapped = _COUNTRY_NAME_TO_ISO2.get(normalized)
    if mapped:
        return mapped

    if len(normalized) == 2:
        return normalized

    logger.warning(f"JSearch: unrecognized country {country!r}, defaulting to 'us'")
    return "us"


# Backward-compatible alias: existing internal call sites/tests reference the
# underscore-prefixed name. Kept as a plain alias (not a re-implementation) so
# behavior is identical either way this chunk's own "no other change to this
# function" constraint requires.
_country_to_iso2 = country_to_iso2


def _language_for_country(country_iso2: str) -> str | None:
    """Non-English-primary-market language override for JSearch's "language" param.

    Returns None (omit the param) for markets where JSearch's own
    country-based default is already correct — only markets with a documented
    mismatch (see _COUNTRY_ISO2_TO_LANGUAGE above) get an explicit override.
    """
    return _COUNTRY_ISO2_TO_LANGUAGE.get(country_iso2.lower())


def _normalize_publisher(raw: str | None) -> str:
    """Map a free-text JSearch publisher/board name to one of a closed set of 6 literals.

    The only values this function may ever return are: "linkedin", "indeed", "glassdoor",
    "zip_recruiter", "google", or the catch-all "jsearch_other". This is a fixed vocabulary
    agreed by convention with app/enrichers/merge.py's own hardcoded literal filter set —
    there is intentionally no shared constant or import for this contract. Keeping the
    vocabulary closed (instead of minting a bespoke slug per unrecognized publisher) bounds
    Prometheus metric label cardinality and job-posting dedup-key cardinality.
    """
    if not raw or not raw.strip():
        return "jsearch_other"

    normalized = raw.strip().lower()
    for alias, slug in _PUBLISHER_ALIASES:
        if alias in normalized:
            return slug

    return "jsearch_other"


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

        # Try LLM optimization first if enabled. Skipped for JSearch: it takes one broad
        # query rather than per-board optimized queries, so calling the LLM here would be
        # a wasted API call.
        optimized_queries = None
        jsearch_mode = settings.job_source_provider == "jsearch"
        if not jsearch_mode and settings.llm_mode.strip().lower() == "litellm":
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
        settings = get_settings()
        if settings.job_source_provider == "jsearch":
            return self._scrape_jsearch(search_term, location, country, limit)

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

    def _scrape_jsearch(
        self,
        search_term: str,
        location: str | None,
        country: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fetch job postings from the JSearch RapidAPI endpoint.

        Deliberately a plain sync method using a sync ``httpx.Client`` (not
        ``httpx.AsyncClient``/``asyncio.run``): ``_scrape`` is called from two contexts —
        `_fetch` and `job_matching.py::_scan_jobs_for_candidate_async` — and both currently
        wrap the call in ``asyncio.to_thread``, but using a sync HTTP client here sidesteps
        the "asyncio.run() cannot be called from a running event loop" failure mode entirely
        rather than depending on both call sites never invoking `_scrape` directly from a
        running loop. Self-sufficient retry/backoff below matches `_scrape`'s contract: never
        raises, always returns a (possibly empty) list.
        """
        settings = get_settings()
        if not settings.jsearch_api_key:
            logger.warning("JSearch API key not configured")
            return []

        query = f"{search_term} in {location}" if location else search_term
        iso2_country = _country_to_iso2(country)
        params = {
            "query": query,
            "num_pages": str(settings.jsearch_num_pages),
            "country": iso2_country,
            "date_posted": "all",
        }
        language = _language_for_country(iso2_country)
        if language:
            params["language"] = language
        headers = {
            "X-RapidAPI-Key": settings.jsearch_api_key,
            "X-RapidAPI-Host": settings.jsearch_api_host,
        }
        # /search-v2 (not the legacy /search) reliably returns job_description inline,
        # avoiding a second per-job /job-details call that would double API/token cost.
        url = f"https://{settings.jsearch_api_host}/search-v2"

        max_attempts = 3
        response: httpx.Response | None = None
        for attempt in range(max_attempts):
            try:
                with httpx.Client(timeout=settings.jsearch_timeout_seconds) as client:
                    response = client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                break
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status == 429 or status >= 500:
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"JSearch request failed with status {status}, "
                            f"retrying (attempt {attempt + 1}/{max_attempts})"
                        )
                        time.sleep(2**attempt)
                        continue
                    logger.error(f"JSearch request failed after {max_attempts} attempts: {e}")
                    return []
                # Non-retryable 4xx (e.g. 401/403 bad key) - fail fast, no retry.
                logger.error(f"JSearch request failed with non-retryable status {status}: {e}")
                return []
            except (httpx.TimeoutException, httpx.TransportError) as e:
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"JSearch request error: {e}, retrying (attempt {attempt + 1}/{max_attempts})"
                    )
                    time.sleep(2**attempt)
                    continue
                logger.error(f"JSearch request failed after {max_attempts} attempts: {e}")
                return []
            except Exception as e:
                logger.error(f"JSearch request failed unexpectedly: {e}", exc_info=True)
                return []

        if response is None:
            return []

        try:
            payload = response.json()
        except Exception as e:
            logger.error(f"Failed to parse JSearch response JSON: {e}")
            return []

        # /search-v2's "data" has been observed in two shapes: a flat list of job
        # objects (legacy/documented shape), and {"jobs": [...], "cursor": ...}
        # (current live shape, added for cursor-based pagination). Accept both so a
        # future provider-side revert doesn't silently zero out every scrape again.
        raw_data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(raw_data, dict):
            data = raw_data.get("jobs")
        else:
            data = raw_data
        if not isinstance(data, list):
            logger.warning("JSearch response missing 'data'/'data.jobs' array")
            return []

        rows: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "title": item.get("job_title") or "",
                    "company": item.get("employer_name") or "",
                    "location": ", ".join(
                        filter(
                            None,
                            [
                                item.get("job_city"),
                                item.get("job_state"),
                                item.get("job_country"),
                            ],
                        )
                    )
                    or (location or ""),
                    "is_remote": bool(item.get("job_is_remote") or False),
                    "site": _normalize_publisher(item.get("job_publisher") or ""),
                    "description": item.get("job_description") or "",
                }
            )

        logger.info(f"JSearch returned {len(rows)} jobs (limit={limit})")
        return rows[:limit]

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
