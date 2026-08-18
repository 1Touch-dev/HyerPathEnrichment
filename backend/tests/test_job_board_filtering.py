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
    google_job = {"title": "Engineer", "company": "Acme", "location": "NYC", "source": "google"}

    # For work history (no job_search), job boards should be filtered
    assert _is_valid_job(indeed_job, is_job_search=False) is False
    assert _is_valid_job(glassdoor_job, is_job_search=False) is False
    assert _is_valid_job(zip_job, is_job_search=False) is False

    # But LinkedIn and Google work history should be kept
    assert _is_valid_job(linkedin_job, is_job_search=False) is True
    assert _is_valid_job(google_job, is_job_search=False) is True


@pytest.mark.parametrize(
    "source",
    [
        "indeed",
        "Indeed",
        "INDEED",
        "glassdoor",
        "Glassdoor",
        "GLASSDOOR",
        "zip_recruiter",
        "Zip_Recruiter",
        "ZIP_RECRUITER",
    ],
)
def test_job_board_sources_filtered_case_insensitive(source: str) -> None:
    """Excluded job-board sources are filtered regardless of casing."""
    job = {"title": "Engineer", "company": "Acme", "location": "NYC", "source": source}
    assert _is_valid_job(job, is_job_search=False) is False


def test_jsearch_other_catchall_filtered_for_work_history() -> None:
    """The 'jsearch_other' catch-all publisher bucket is excluded from work history."""
    job = {"title": "Engineer", "company": "Acme", "location": "NYC", "source": "jsearch_other"}
    assert _is_valid_job(job, is_job_search=False) is False


def test_jsearch_other_catchall_filtered_case_insensitive() -> None:
    """The 'jsearch_other' exclusion is case-insensitive."""
    job = {"title": "Engineer", "company": "Acme", "location": "NYC", "source": "JSearch_Other"}
    assert _is_valid_job(job, is_job_search=False) is False


def test_jsearch_other_kept_for_job_search() -> None:
    """For job searches (tier4), 'jsearch_other' listings are kept like any other source."""
    job = {"title": "Engineer", "company": "Acme", "location": "NYC", "source": "jsearch_other"}
    assert _is_valid_job(job, is_job_search=True) is True


def test_merge_module_has_no_jobspy_dependency() -> None:
    """The excluded-source vocabulary in merge.py must be a local literal, not imported
    from app.enrichers.jobspy (fixed vocabulary contract, no cross-import by design)."""
    import ast
    import inspect

    import app.enrichers.merge as merge_module

    assert not hasattr(merge_module, "WORK_HISTORY_EXCLUDED_SOURCES")

    # AST-level guard: no import statement in merge.py may reference
    # app.enrichers.jobspy (comments/docstrings mentioning it are fine).
    source = inspect.getsource(merge_module)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "app.enrichers.jobspy"
        elif isinstance(node, ast.Import):
            assert all(alias.name != "app.enrichers.jobspy" for alias in node.names)

    assert "_WORK_HISTORY_EXCLUDED_SOURCES" in merge_module.__dict__
    assert merge_module._WORK_HISTORY_EXCLUDED_SOURCES == {
        "indeed",
        "glassdoor",
        "zip_recruiter",
        "jsearch_other",
    }


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
