"""Job merge deduplication across boards and locations."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.models import EnrichmentRequest
from app.workers.runner import PipelineOrchestrator


@pytest.fixture
def orchestrator() -> PipelineOrchestrator:
    return PipelineOrchestrator(db=AsyncMock())


def _job(
    *,
    title: str,
    company: str,
    location: str,
    source: str,
    remote: bool = False,
) -> dict[str, Any]:
    return {
        "title": title,
        "company": company,
        "location": location,
        "remote": remote,
        "source": source,
    }


@pytest.mark.asyncio
async def test_merge_dedupes_same_role_across_boards(orchestrator: PipelineOrchestrator) -> None:
    request = EnrichmentRequest(job_search="software engineer")
    payloads: list[dict[str, Any]] = [
        {
            "jobs": [
                _job(
                    title="Software Engineer",
                    company="Acme Inc.",
                    location="San Francisco, CA",
                    source="linkedin",
                )
            ],
            "sources": ["linkedin"],
        },
        {
            "jobs": [
                _job(
                    title="Software Engineer!",
                    company="Acme LLC",
                    location="San Francisco, CA",
                    source="indeed",
                )
            ],
            "sources": ["indeed"],
        },
    ]

    dossier = await orchestrator._merge(request, payloads)

    assert len(dossier.jobs) == 1
    assert dossier.jobs[0].source == "linkedin"


@pytest.mark.asyncio
async def test_merge_keeps_different_locations_as_separate_jobs(
    orchestrator: PipelineOrchestrator,
) -> None:
    request = EnrichmentRequest(job_search="software engineer")
    payloads: list[dict[str, Any]] = [
        {
            "jobs": [
                _job(
                    title="Software Engineer",
                    company="Acme Inc.",
                    location="San Francisco, CA",
                    source="linkedin",
                ),
                _job(
                    title="Software Engineer",
                    company="Acme Inc.",
                    location="New York, NY",
                    source="indeed",
                ),
            ],
            "sources": ["linkedin", "indeed"],
        }
    ]

    dossier = await orchestrator._merge(request, payloads)

    assert len(dossier.jobs) == 2
    locations = {job.location for job in dossier.jobs}
    assert locations == {"San Francisco, CA", "New York, NY"}


@pytest.mark.asyncio
async def test_merge_dedupes_exact_duplicate(orchestrator: PipelineOrchestrator) -> None:
    request = EnrichmentRequest(job_search="software engineer")
    job = _job(
        title="Backend Developer",
        company="Globex",
        location="Remote",
        source="linkedin",
        remote=True,
    )
    payloads: list[dict[str, Any]] = [
        {"jobs": [job], "sources": ["linkedin"]},
        {"jobs": [dict(job)], "sources": ["linkedin"]},
    ]

    dossier = await orchestrator._merge(request, payloads)

    assert len(dossier.jobs) == 1
    assert dossier.jobs[0].title == "Backend Developer"
    assert dossier.jobs[0].remote is True
