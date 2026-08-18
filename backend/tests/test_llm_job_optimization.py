"""Tests for LLM job query optimization."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.llm import (
    _parse_job_queries,
    build_job_query_messages,
    litellm_optimize_job_query,
)
from app.core.config import Settings
from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import RequestedTier
from app.enrichers.jobspy import JobSpyEnricher


@pytest.fixture
def mock_settings() -> Settings:
    """Mock settings with LiteLLM configured."""
    settings = Settings()
    settings.llm_mode = "litellm"
    settings.litellm_api_base = "http://litellm:4000"
    settings.litellm_model = "gemini/gemini-2.5-flash"
    settings.litellm_fallbacks = ""
    settings.litellm_api_key = ""
    return settings


@pytest.fixture
def sample_llm_response() -> dict[str, dict[str, str]]:
    """Sample LLM-optimized job queries."""
    return {
        "linkedin": {
            "search_term": "Software Engineer",
            "location": "Bengaluru, Karnataka, India",
        },
        "indeed": {
            "search_term": "Software Engineer",
            "location": "Bengaluru, Karnataka",
            "country_indeed": "india",
        },
        "glassdoor": {
            "search_term": "Software Engineer",
            "location": "Bengaluru, Karnataka",
        },
        "google": {
            "google_search_term": "Software Engineer jobs in Bengaluru, Karnataka, India",
        },
        "zip_recruiter": {
            "search_term": "Software Engineer",
            "location": "Bengaluru, India",
        },
    }


def test_build_job_query_messages() -> None:
    """Test message builder for job query optimization."""
    messages = build_job_query_messages("Software Engineer", "Mumbai", "India")

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Software Engineer" in messages[1]["content"]
    assert "Mumbai" in messages[1]["content"]
    assert "India" in messages[1]["content"]


def test_build_job_query_messages_with_none_location() -> None:
    """Test message builder with None location/country."""
    messages = build_job_query_messages("Data Scientist", None, None)

    assert len(messages) == 2
    assert "Data Scientist" in messages[1]["content"]
    assert "None" in messages[1]["content"]


def test_parse_job_queries_success(sample_llm_response: dict) -> None:
    """Test parsing valid LLM response."""
    import json

    content = json.dumps(sample_llm_response)
    result = _parse_job_queries(content)

    assert result is not None
    assert "linkedin" in result
    assert "indeed" in result
    assert "glassdoor" in result
    assert "google" in result
    assert "zip_recruiter" in result
    assert result["linkedin"]["search_term"] == "Software Engineer"
    assert result["indeed"]["country_indeed"] == "india"


def test_parse_job_queries_with_markdown() -> None:
    """Test parsing LLM response wrapped in markdown."""
    content = """```json
{
  "linkedin": {"search_term": "Engineer", "location": "Mumbai"},
  "indeed": {"search_term": "Engineer", "location": "Mumbai", "country_indeed": "india"},
  "glassdoor": {"search_term": "Engineer", "location": "Mumbai"},
  "google": {"google_search_term": "Engineer jobs in Mumbai"},
  "zip_recruiter": {"search_term": "Engineer", "location": "Mumbai"}
}
```"""

    result = _parse_job_queries(content)
    assert result is not None
    assert "linkedin" in result


def test_parse_job_queries_missing_board() -> None:
    """Test parsing fails when a board is missing."""
    content = """{
  "linkedin": {"search_term": "Engineer", "location": "Mumbai"},
  "indeed": {"search_term": "Engineer", "location": "Mumbai"}
}"""

    result = _parse_job_queries(content)
    assert result is None


def test_parse_job_queries_invalid_json() -> None:
    """Test parsing fails with invalid JSON."""
    content = "This is not valid JSON at all"
    result = _parse_job_queries(content)
    assert result is None


@pytest.mark.asyncio
async def test_litellm_optimize_job_query_success(
    mock_settings: Settings,
    sample_llm_response: dict,
) -> None:
    """Test successful LLM optimization."""
    import json

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(sample_llm_response)}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        result = await litellm_optimize_job_query(
            "Software Engineer", "Bengaluru", "India", mock_settings
        )

        assert result is not None
        assert "linkedin" in result
        assert "indeed" in result
        assert result["linkedin"]["search_term"] == "Software Engineer"
        assert result["indeed"]["country_indeed"] == "india"


@pytest.mark.asyncio
async def test_litellm_optimize_job_query_no_config(mock_settings: Settings) -> None:
    """Test returns None when LiteLLM not configured."""
    mock_settings.litellm_api_base = ""

    result = await litellm_optimize_job_query("Software Engineer", "Mumbai", "India", mock_settings)

    assert result is None


@pytest.mark.asyncio
async def test_litellm_optimize_job_query_http_error(mock_settings: Settings) -> None:
    """Test fallback when HTTP error occurs."""
    import httpx

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.HTTPError("Connection failed")
        )

        result = await litellm_optimize_job_query(
            "Software Engineer", "Mumbai", "India", mock_settings
        )

        assert result is None


@pytest.mark.asyncio
async def test_litellm_optimize_job_query_invalid_response(
    mock_settings: Settings,
) -> None:
    """Test fallback when LLM returns invalid format."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Invalid response format"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        result = await litellm_optimize_job_query(
            "Software Engineer", "Mumbai", "India", mock_settings
        )

        assert result is None


@pytest.mark.asyncio
async def test_litellm_optimize_job_query_fallback_chain(
    mock_settings: Settings,
    sample_llm_response: dict,
) -> None:
    """Test fallback chain tries multiple models."""
    import json

    import httpx

    mock_settings.litellm_fallbacks = "gpt-4o-mini"

    # First call fails, second succeeds
    success_response = MagicMock()
    success_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(sample_llm_response)}}]
    }
    success_response.raise_for_status = MagicMock()

    call_count = 0

    async def mock_post(*args: Any, **kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.HTTPError("First model failed")
        return success_response

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await litellm_optimize_job_query(
            "Software Engineer", "Mumbai", "India", mock_settings
        )

        assert result is not None
        assert call_count == 2  # Tried both models


@pytest.mark.asyncio
async def test_fetch_still_calls_llm_optimization_for_default_jobspy_provider(
    sample_llm_response: dict[str, dict[str, str]],
) -> None:
    """Regression guard for the JSearch-migration's LLM-gating change (jobspy.py's
    `_fetch`): with `job_source_provider` left at its default ("jobspy") and
    `llm_mode="litellm"`, the opt-in per-board query-optimization call must still fire
    exactly as before. The equivalent real end-to-end test below
    (`test_jobspy_fetch_with_llm_enabled`) is skipped on Windows because it imports the
    real `jobspy` package; this test proves the same gating contract without that import
    by patching `_scrape` directly on the instance, the same technique
    `test_jsearch_provider.py` uses for its jsearch-path equivalent."""
    enricher = JobSpyEnricher()
    request = EnrichmentRequest(
        job_title="Software Engineer",
        job_location="Mumbai",
        job_country="India",
        job_search="Software Engineer Mumbai",
        requested_tiers=[RequestedTier.tier4],
    )

    settings = Settings()
    assert settings.job_source_provider == "jobspy"
    settings.llm_mode = "litellm"

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch(
            "app.clients.llm.litellm_optimize_job_query",
            new_callable=AsyncMock,
            return_value=sample_llm_response,
        ) as mock_optimize:
            with patch.object(enricher, "_scrape", return_value=[]) as mock_scrape:
                await enricher._fetch(request)

    mock_optimize.assert_called_once()
    mock_scrape.assert_called_once()
    # The LLM-optimized queries must be threaded through to _scrape as its last
    # positional argument (the `optimized_queries` param), not silently dropped.
    assert mock_scrape.call_args[0][-1] == sample_llm_response


@pytest.mark.asyncio
async def test_fetch_jsearch_gating_never_invokes_llm_module_spy_even_with_results() -> None:
    """Complementary regression layer to `test_jsearch_provider.py`'s
    `test_fetch_skips_llm_optimization_when_jsearch` (which also patches
    `app.clients.llm.litellm_optimize_job_query` and asserts it's not called, but with an
    empty `_scrape` result). This test intentionally differs by installing the spy
    directly on the `app.clients.llm` module attribute (via `patch.object` on the
    module, rather than the string-target `patch("app.clients.llm.litellm_optimize_job_query")`
    form), and by returning *non-empty* scrape rows -- proving the gating holds even when
    there is real job data to optimize a query for, from this file's own vantage point as
    the authoritative suite for `litellm_optimize_job_query`.
    """
    import app.clients.llm as llm_module

    enricher = JobSpyEnricher()
    request = EnrichmentRequest(
        job_title="Software Engineer",
        job_location="Mumbai",
        job_country="India",
        job_search="Software Engineer Mumbai",
        requested_tiers=[RequestedTier.tier4],
    )

    settings = Settings()
    settings.job_source_provider = "jsearch"
    settings.llm_mode = "litellm"

    spy = MagicMock(wraps=llm_module.litellm_optimize_job_query)
    scraped_rows = [
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "site": "jsearch_other",
            "location": "Mumbai",
        }
    ]

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch.object(llm_module, "litellm_optimize_job_query", spy):
            with patch.object(enricher, "_scrape", return_value=scraped_rows):
                result = await enricher._fetch(request)

    spy.assert_not_called()
    assert result["jobs"][0]["title"] == "Backend Engineer"
    assert result["jobs"][0]["source"] == "jsearch_other"


@pytest.mark.asyncio
@pytest.mark.skip(reason="JobSpy import causes Windows access violation in test environment")
async def test_jobspy_enricher_uses_llm_optimization() -> None:
    """Test JobSpyEnricher uses LLM optimization when available."""
    enricher = JobSpyEnricher()

    # Mock the scrape_jobs function
    with patch("jobspy.scrape_jobs") as mock_scrape:
        mock_scrape.return_value = MagicMock(
            empty=False,
            to_dict=lambda orient: [{"title": "Engineer", "company": "Acme", "site": "linkedin"}],
        )

        optimized_queries = {
            "linkedin": {"search_term": "Software Engineer", "location": "Mumbai, India"},
            "indeed": {
                "search_term": "Software Engineer",
                "location": "Mumbai",
                "country_indeed": "india",
            },
            "glassdoor": {"search_term": "Software Engineer", "location": "Mumbai"},
            "google": {"google_search_term": "Software Engineer jobs in Mumbai, India"},
            "zip_recruiter": {"search_term": "Software Engineer", "location": "Mumbai"},
        }

        rows = enricher._scrape(
            "Software Engineer",
            "Mumbai",
            "India",
            None,
            15,
            optimized_queries,
        )

        assert len(rows) > 0

        # Check that scrape_jobs was called with optimized parameters
        call_kwargs = mock_scrape.call_args[1]
        assert call_kwargs["search_term"] == "Software Engineer"
        assert call_kwargs["location"] == "Mumbai, India"
        assert call_kwargs["country_indeed"] == "india"
        assert call_kwargs["google_search_term"] == "Software Engineer jobs in Mumbai, India"


@pytest.mark.asyncio
@pytest.mark.skip(reason="JobSpy import causes Windows access violation in test environment")
async def test_jobspy_enricher_fallback_without_llm() -> None:
    """Test JobSpyEnricher uses manual logic when LLM not available."""
    enricher = JobSpyEnricher()

    with patch("jobspy.scrape_jobs") as mock_scrape:
        mock_scrape.return_value = MagicMock(
            empty=False,
            to_dict=lambda orient: [{"title": "Engineer", "company": "Acme", "site": "linkedin"}],
        )

        # Pass None for optimized_queries to trigger manual logic
        rows = enricher._scrape(
            "Software Engineer",
            "Mumbai",
            "India",
            None,
            15,
            None,  # No LLM optimization
        )

        assert len(rows) > 0

        # Check that scrape_jobs was called with manual parameters
        call_kwargs = mock_scrape.call_args[1]
        assert call_kwargs["search_term"] == "Software Engineer"
        assert call_kwargs["location"] == "Mumbai, India"
        assert call_kwargs["country_indeed"] == "india"


def test_jobspy_build_kwargs_manual() -> None:
    """Test manual kwargs building."""
    enricher = JobSpyEnricher()

    kwargs = enricher._build_kwargs_manual("Software Engineer", "Mumbai", "India", 15)

    assert kwargs["search_term"] == "Software Engineer"
    assert kwargs["location"] == "Mumbai, India"
    assert kwargs["country_indeed"] == "india"
    assert kwargs["results_wanted"] == 15
    assert "google_search_term" in kwargs


@pytest.mark.asyncio
@pytest.mark.skip(reason="JobSpy import causes Windows access violation in test environment")
async def test_jobspy_fetch_with_llm_enabled() -> None:
    """Test _fetch method with LLM optimization enabled."""
    enricher = JobSpyEnricher()
    request = EnrichmentRequest(
        job_title="Software Engineer",
        job_location="Mumbai",
        job_country="India",
        job_search="Software Engineer Mumbai",
        requested_tiers=["tier4"],
    )

    sample_queries = {
        "linkedin": {"search_term": "Software Engineer", "location": "Mumbai, India"},
        "indeed": {
            "search_term": "Software Engineer",
            "location": "Mumbai",
            "country_indeed": "india",
        },
        "glassdoor": {"search_term": "Software Engineer", "location": "Mumbai"},
        "google": {"google_search_term": "Software Engineer jobs in Mumbai, India"},
        "zip_recruiter": {"search_term": "Software Engineer", "location": "Mumbai"},
    }

    with patch("app.core.config.get_settings") as mock_get_settings:
        mock_settings = Settings()
        mock_settings.llm_mode = "litellm"
        mock_settings.jobspy_results_per_board = 15
        mock_get_settings.return_value = mock_settings

        with patch("app.clients.llm.litellm_optimize_job_query") as mock_optimize:
            mock_optimize.return_value = sample_queries

            with patch("jobspy.scrape_jobs") as mock_scrape:
                mock_scrape.return_value = MagicMock(
                    empty=False,
                    to_dict=lambda orient: [
                        {
                            "title": "Software Engineer",
                            "company": "Acme",
                            "site": "linkedin",
                            "location": "Mumbai",
                            "is_remote": False,
                        }
                    ],
                )

                result = await enricher._fetch(request)

                assert "jobs" in result
                assert len(result["jobs"]) > 0
                assert result["jobs"][0]["title"] == "Software Engineer"

                # Verify LLM optimization was called
                mock_optimize.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
