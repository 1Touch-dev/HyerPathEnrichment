"""Test that job board filtering works correctly for job searches vs work history."""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.enrichment import EnrichmentRequest
from app.enrichers.merge import _is_valid_job, merge_payloads


def test_job_board_sources_kept_for_job_search() -> None:
    """When job_search is present (tier4), keep Indeed/Glassdoor/ZipRecruiter jobs."""
    indeed_job = {"title": "Engineer", "company": "Acme", "location": "NYC", "source": "indeed"}
    glassdoor_job = {
        "title": "Engineer",
        "company": "Acme",
        "location": "NYC",
        "source": "glassdoor",
    }
    zip_job = {"title": "Engineer", "company": "Acme", "location": "NYC", "source": "zip_recruiter"}

    # For job searches (tier4), all job boards should be valid
    assert _is_valid_job(indeed_job, is_job_search=True) is True
    assert _is_valid_job(glassdoor_job, is_job_search=True) is True
    assert _is_valid_job(zip_job, is_job_search=True) is True


def test_job_board_sources_filtered_for_work_history() -> None:
    """When job_search is absent (LinkedIn profile), filter out job boards."""
    indeed_job = {"title": "Engineer", "company": "Acme", "location": "NYC", "source": "indeed"}
    glassdoor_job = {
        "title": "Engineer",
        "company": "Acme",
        "location": "NYC",
        "source": "glassdoor",
    }
    zip_job = {"title": "Engineer", "company": "Acme", "location": "NYC", "source": "zip_recruiter"}
    linkedin_job = {"title": "Engineer", "company": "Acme", "location": "NYC", "source": "linkedin"}

    # For work history (no job_search), job boards should be filtered
    assert _is_valid_job(indeed_job, is_job_search=False) is False
    assert _is_valid_job(glassdoor_job, is_job_search=False) is False
    assert _is_valid_job(zip_job, is_job_search=False) is False

    # But LinkedIn work history should be kept
    assert _is_valid_job(linkedin_job, is_job_search=False) is True


def test_invalid_companies_always_filtered() -> None:
    """Invalid company names should be filtered regardless of context."""
    invalid_jobs = [
        {"title": "Engineer", "company": "NaN", "location": "NYC", "source": "linkedin"},
        {"title": "Engineer", "company": "none", "location": "NYC", "source": "indeed"},
        {"title": "Engineer", "company": "", "location": "NYC", "source": "glassdoor"},
        {"title": "Engineer", "company": "unknown", "location": "NYC", "source": "zip_recruiter"},
    ]

    for job in invalid_jobs:
        assert _is_valid_job(job, is_job_search=True) is False
        assert _is_valid_job(job, is_job_search=False) is False


@pytest.mark.asyncio
async def test_merge_keeps_all_job_boards_for_tier4() -> None:
    """Integration test: merge_payloads should keep all job boards for tier4."""
    request = EnrichmentRequest(
        job_search="software engineer",
        job_title="software engineer",
        job_location="San Francisco",
        requested_tiers=["tier4"],
    )

    payloads: list[dict[str, Any]] = [
        {
            "jobs": [
                {
                    "title": "SWE",
                    "company": "CompanyA",
                    "location": "SF",
                    "source": "linkedin",
                    "remote": False,
                },
                {
                    "title": "SWE",
                    "company": "CompanyB",
                    "location": "SF",
                    "source": "indeed",
                    "remote": False,
                },
                {
                    "title": "SWE",
                    "company": "CompanyC",
                    "location": "SF",
                    "source": "glassdoor",
                    "remote": False,
                },
                {
                    "title": "SWE",
                    "company": "CompanyD",
                    "location": "SF",
                    "source": "zip_recruiter",
                    "remote": False,
                },
                {
                    "title": "SWE",
                    "company": "CompanyE",
                    "location": "SF",
                    "source": "google",
                    "remote": False,
                },
            ],
            "sources": ["JobSpy"],
        }
    ]

    dossier = merge_payloads(request, payloads)

    # All 5 jobs should be kept (LinkedIn + 4 job boards)
    assert len(dossier.jobs) == 5
    sources = {job.source for job in dossier.jobs}
    assert sources == {"linkedin", "indeed", "glassdoor", "zip_recruiter", "google"}


@pytest.mark.asyncio
async def test_merge_filters_job_boards_for_work_history() -> None:
    """Integration test: merge_payloads should filter job boards for LinkedIn profiles."""
    request = EnrichmentRequest(
        linkedin_url="https://linkedin.com/in/johndoe",  # LinkedIn profile context
        requested_tiers=["tier1"],
    )

    payloads: list[dict[str, Any]] = [
        {
            "jobs": [
                {
                    "title": "SWE",
                    "company": "CompanyA",
                    "location": "SF",
                    "source": "linkedin",
                    "remote": False,
                },
                {
                    "title": "SWE",
                    "company": "CompanyB",
                    "location": "SF",
                    "source": "indeed",
                    "remote": False,
                },
                {
                    "title": "SWE",
                    "company": "CompanyC",
                    "location": "SF",
                    "source": "glassdoor",
                    "remote": False,
                },
            ],
            "sources": ["LinkedIn"],
        }
    ]

    dossier = merge_payloads(request, payloads)

    # Only LinkedIn job should be kept (Indeed/Glassdoor filtered out)
    assert len(dossier.jobs) == 1
    assert dossier.jobs[0].source == "linkedin"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
