"""Tests for the JSearch (RapidAPI) job-source provider in app.enrichers.jobspy.

Covers `_normalize_publisher`'s closed 6-value vocabulary, the `job_source_provider`
config-flag branch inside `_scrape`/`_scrape_jsearch`, and the LLM-optimizer gating in
`_fetch`. All HTTP calls are mocked (no live network per RULE.md "No live external calls
in CI").
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.config import Settings
from app.domain.enrichment import EnrichmentRequest
from app.enrichers.jobspy import JobSpyEnricher, _normalize_publisher

# ---------------------------------------------------------------------------
# _normalize_publisher: closed 6-value vocabulary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("linkedin", "linkedin"),
        ("LinkedIn", "linkedin"),
        ("LINKEDIN", "linkedin"),
        ("indeed", "indeed"),
        ("Indeed", "indeed"),
        ("glassdoor", "glassdoor"),
        ("Glassdoor", "glassdoor"),
        ("zip recruiter", "zip_recruiter"),
        ("Zip Recruiter", "zip_recruiter"),
        ("ziprecruiter", "zip_recruiter"),
        ("ZipRecruiter", "zip_recruiter"),
        ("zip_recruiter", "zip_recruiter"),
        ("google", "google"),
        ("Google", "google"),
        ("Google Jobs", "google"),
        ("google jobs", "google"),
    ],
)
def test_normalize_publisher_known_aliases(raw: str, expected: str) -> None:
    assert _normalize_publisher(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["Monster", "CareerBuilder", "Built In", "Monster.com", "", None, "   "],
)
def test_normalize_publisher_unknown_falls_back_to_jsearch_other(raw: str | None) -> None:
    """Unrecognized publishers (and empty/None input) normalize to the single literal
    "jsearch_other" -- NOT a bespoke per-publisher slug."""
    assert _normalize_publisher(raw) == "jsearch_other"


def test_normalize_publisher_vocabulary_is_closed() -> None:
    """The only values _normalize_publisher may ever emit are these 6 literals."""
    allowed = {"linkedin", "indeed", "glassdoor", "zip_recruiter", "google", "jsearch_other"}
    sample_inputs = [
        "linkedin",
        "Indeed",
        "GLASSDOOR",
        "Zip Recruiter",
        "Google Jobs",
        "Monster",
        "CareerBuilder",
        "Some Random Board",
        "",
        None,
    ]
    for raw in sample_inputs:
        assert _normalize_publisher(raw) in allowed


# ---------------------------------------------------------------------------
# _scrape: job_source_provider="jobspy" (default) is completely unaffected
# ---------------------------------------------------------------------------


def test_scrape_default_jobspy_path_unaffected() -> None:
    """Regression guard: with job_source_provider left at its default ("jobspy"),
    _scrape must still call into the existing python-jobspy code path unchanged."""
    enricher = JobSpyEnricher()
    settings = Settings()
    assert settings.job_source_provider == "jobspy"

    fake_frame = MagicMock(
        empty=False,
        to_dict=lambda orient: [{"title": "Engineer", "company": "Acme", "site": "linkedin"}],
    )

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch.dict(
            "sys.modules", {"jobspy": MagicMock(scrape_jobs=MagicMock(return_value=fake_frame))}
        ):
            import sys

            mock_scrape_jobs = sys.modules["jobspy"].scrape_jobs
            rows = enricher._scrape("Software Engineer", "Mumbai", "India", None, 15, None)

    assert mock_scrape_jobs.called
    assert len(rows) == 1
    assert rows[0]["site"] == "linkedin"


def test_scrape_default_jobspy_does_not_call_jsearch(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the default provider, _scrape_jsearch must never be invoked."""
    enricher = JobSpyEnricher()
    settings = Settings()

    called = {"jsearch": False}

    def _fail_if_called(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        called["jsearch"] = True
        return []

    monkeypatch.setattr(enricher, "_scrape_jsearch", _fail_if_called)

    fake_frame = MagicMock(empty=True)
    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch.dict(
            "sys.modules",
            {"jobspy": MagicMock(scrape_jobs=MagicMock(return_value=fake_frame))},
        ):
            enricher._scrape("Software Engineer", "Mumbai", "India", None, 15, None)

    assert called["jsearch"] is False


# ---------------------------------------------------------------------------
# _scrape / _scrape_jsearch with job_source_provider="jsearch"
# ---------------------------------------------------------------------------


def _jsearch_settings(**overrides: Any) -> Settings:
    settings = Settings()
    settings.job_source_provider = "jsearch"
    settings.jsearch_api_key = "test-api-key"
    settings.jsearch_api_host = "jsearch.p.rapidapi.com"
    settings.jsearch_num_pages = 1
    settings.jsearch_timeout_seconds = 20.0
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _mock_response(status_code: int, json_payload: dict[str, Any] | None = None) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    if json_payload is not None:
        response.json.return_value = json_payload
    if status_code >= 400:
        request = httpx.Request("GET", "https://jsearch.p.rapidapi.com/search-v2")
        error = httpx.HTTPStatusError("error", request=request, response=response)
        response.raise_for_status.side_effect = error
    else:
        response.raise_for_status.return_value = None
    return response


def test_scrape_jsearch_calls_search_v2_endpoint_with_expected_params() -> None:
    """Must call /search-v2 (not the legacy /search) so job_description is returned
    inline, avoiding a second per-job /job-details call. Regression guard for a bug
    where the URL pointed at /search."""
    enricher = JobSpyEnricher()
    settings = _jsearch_settings()
    response = _mock_response(200, {"data": []})

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch("httpx.Client") as mock_client_cls:
            mock_get = mock_client_cls.return_value.__enter__.return_value.get
            mock_get.return_value = response
            enricher._scrape_jsearch("Software Engineer", "Bengaluru", "India", 15)

    mock_get.assert_called_once()
    call_args, call_kwargs = mock_get.call_args
    url = call_args[0] if call_args else call_kwargs["url"]
    assert url == "https://jsearch.p.rapidapi.com/search-v2"
    params = call_kwargs["params"]
    assert params["query"] == "Software Engineer in Bengaluru"
    assert params["num_pages"] == "1"
    assert params["country"] == "india"
    assert params["date_posted"] == "all"


def test_scrape_jsearch_rows_shaped_correctly() -> None:
    enricher = JobSpyEnricher()
    settings = _jsearch_settings()

    payload = {
        "data": [
            {
                "job_title": "Backend Engineer",
                "employer_name": "Acme Corp",
                "job_city": "Bengaluru",
                "job_state": "Karnataka",
                "job_country": "IN",
                "job_is_remote": True,
                "job_publisher": "LinkedIn",
                "job_description": "Build backend services.",
            }
        ]
    }
    response = _mock_response(200, payload)

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = response
            rows = enricher._scrape_jsearch("Software Engineer", "Bengaluru", "India", 15)

    assert len(rows) == 1
    row = rows[0]
    for key in ("title", "company", "location", "is_remote", "site", "description"):
        assert key in row
    assert row["title"] == "Backend Engineer"
    assert row["company"] == "Acme Corp"
    assert row["location"] == "Bengaluru, Karnataka, IN"
    assert row["is_remote"] is True
    assert row["site"] == "linkedin"
    assert row["description"] == "Build backend services."


def test_scrape_jsearch_respects_limit() -> None:
    enricher = JobSpyEnricher()
    settings = _jsearch_settings()

    payload = {
        "data": [
            {"job_title": f"Role {i}", "employer_name": "Acme", "job_publisher": "Indeed"}
            for i in range(10)
        ]
    }
    response = _mock_response(200, payload)

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = response
            rows = enricher._scrape_jsearch("Software Engineer", None, None, 3)

    assert len(rows) == 3


def test_scrape_branches_to_jsearch_when_configured() -> None:
    """_scrape() itself must dispatch to _scrape_jsearch when the flag is set."""
    enricher = JobSpyEnricher()
    settings = _jsearch_settings()

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch.object(enricher, "_scrape_jsearch", return_value=[{"title": "x"}]) as mock_js:
            rows = enricher._scrape("Software Engineer", "Mumbai", "India", None, 15, None)

    mock_js.assert_called_once_with("Software Engineer", "Mumbai", "India", 15)
    assert rows == [{"title": "x"}]


# ---------------------------------------------------------------------------
# Missing API key
# ---------------------------------------------------------------------------


def test_scrape_jsearch_missing_api_key_returns_empty_without_http_call() -> None:
    enricher = JobSpyEnricher()
    settings = _jsearch_settings(jsearch_api_key="")

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch("httpx.Client") as mock_client_cls:
            rows = enricher._scrape_jsearch("Software Engineer", "Mumbai", "India", 15)

    assert rows == []
    mock_client_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Retry / backoff behavior
# ---------------------------------------------------------------------------


def test_scrape_jsearch_retries_then_succeeds_on_429() -> None:
    enricher = JobSpyEnricher()
    settings = _jsearch_settings()

    fail_response = _mock_response(429)
    success_payload = {
        "data": [{"job_title": "Engineer", "employer_name": "Acme", "job_publisher": "Google"}]
    }
    success_response = _mock_response(200, success_payload)

    call_count = {"n": 0}

    def _get(*args: Any, **kwargs: Any) -> MagicMock:
        call_count["n"] += 1
        return fail_response if call_count["n"] == 1 else success_response

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch("httpx.Client") as mock_client_cls, patch("time.sleep") as mock_sleep:
            mock_client_cls.return_value.__enter__.return_value.get.side_effect = _get
            rows = enricher._scrape_jsearch("Software Engineer", None, None, 15)

    assert call_count["n"] == 2
    assert mock_sleep.called
    assert len(rows) == 1
    assert rows[0]["site"] == "google"


def test_scrape_jsearch_exhausted_retries_returns_empty() -> None:
    enricher = JobSpyEnricher()
    settings = _jsearch_settings()

    fail_response = _mock_response(503)

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch("httpx.Client") as mock_client_cls, patch("time.sleep"):
            mock_client_cls.return_value.__enter__.return_value.get.return_value = fail_response
            rows = enricher._scrape_jsearch("Software Engineer", None, None, 15)

    assert rows == []


def test_scrape_jsearch_401_fails_fast_without_retry() -> None:
    """Non-retryable 4xx (bad key) must fail fast -- no retries, single call."""
    enricher = JobSpyEnricher()
    settings = _jsearch_settings()

    fail_response = _mock_response(401)
    call_count = {"n": 0}

    def _get(*args: Any, **kwargs: Any) -> MagicMock:
        call_count["n"] += 1
        return fail_response

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch("httpx.Client") as mock_client_cls, patch("time.sleep") as mock_sleep:
            mock_client_cls.return_value.__enter__.return_value.get.side_effect = _get
            rows = enricher._scrape_jsearch("Software Engineer", None, None, 15)

    assert rows == []
    assert call_count["n"] == 1
    mock_sleep.assert_not_called()


def test_scrape_jsearch_timeout_retries_then_fails() -> None:
    enricher = JobSpyEnricher()
    settings = _jsearch_settings()

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch("httpx.Client") as mock_client_cls, patch("time.sleep") as mock_sleep:
            mock_client_cls.return_value.__enter__.return_value.get.side_effect = (
                httpx.TimeoutException("timed out")
            )
            rows = enricher._scrape_jsearch("Software Engineer", None, None, 15)

    assert rows == []
    assert mock_sleep.call_count == 2  # retried twice before giving up on attempt 3


# ---------------------------------------------------------------------------
# _fetch(): LLM optimizer gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_skips_llm_optimization_when_jsearch() -> None:
    enricher = JobSpyEnricher()
    request = EnrichmentRequest(
        job_title="Software Engineer",
        job_location="Mumbai",
        job_country="India",
        job_search="Software Engineer Mumbai",
        requested_tiers=["tier4"],
    )

    settings = _jsearch_settings()
    settings.llm_mode = "litellm"

    with patch("app.enrichers.jobspy.get_settings", return_value=settings):
        with patch("app.clients.llm.litellm_optimize_job_query") as mock_optimize:
            with patch.object(enricher, "_scrape", return_value=[]):
                await enricher._fetch(request)

    mock_optimize.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
