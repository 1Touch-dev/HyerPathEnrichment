"""Tests for job status clarity — completed vs completed_no_data vs failed."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import JobStatus
from app.enrichers.pipeline import Pipeline


@pytest.mark.asyncio
async def test_job_with_data_shows_completed(db: AsyncSession) -> None:
    """Job that finds enrichment data should have status 'completed'."""
    pipeline = Pipeline(db)

    # Mock enricher that returns photo data
    original_dispatch = pipeline._dispatch

    async def mock_dispatch_with_data(request, sync_mode=False):
        return [
            {
                "photo": {
                    "source": "test-source",
                    "asset_url": "https://example.com/photo.jpg",
                    "captured_at": "2026-07-24T10:00:00Z",
                    "confidence": 0.9,
                },
                "sources": ["test-source"],
            }
        ]

    pipeline._dispatch = mock_dispatch_with_data

    request = EnrichmentRequest(linkedin_url="https://linkedin.com/in/test")
    job = await pipeline.run(request)

    assert job.status == JobStatus.completed.value
    assert job.dossier_payload is not None
    assert job.dossier_payload.get("photo") is not None
    assert "test-source" in job.dossier_payload.get("sources", [])

    pipeline._dispatch = original_dispatch


@pytest.mark.asyncio
async def test_job_with_no_data_shows_completed_no_data(db: AsyncSession) -> None:
    """Job that finds no enrichment data should have status 'completed_no_data'."""
    pipeline = Pipeline(db)

    # Mock enricher that returns empty data
    original_dispatch = pipeline._dispatch

    async def mock_dispatch_no_data(request, sync_mode=False):
        return [{}]

    pipeline._dispatch = mock_dispatch_no_data

    request = EnrichmentRequest(linkedin_url="https://linkedin.com/in/test")
    job = await pipeline.run(request)

    assert job.status == JobStatus.completed_no_data.value
    assert job.dossier_payload is not None
    assert job.dossier_payload.get("photo") is None
    assert len(job.dossier_payload.get("handles", [])) == 0
    assert len(job.dossier_payload.get("emails", [])) == 0
    assert len(job.dossier_payload.get("sources", [])) == 0

    pipeline._dispatch = original_dispatch


@pytest.mark.asyncio
async def test_job_with_handles_shows_completed(db: AsyncSession) -> None:
    """Job that finds social handles should have status 'completed'."""
    pipeline = Pipeline(db)

    original_dispatch = pipeline._dispatch

    async def mock_dispatch_with_handles(request, sync_mode=False):
        return [
            {
                "handles": [
                    {
                        "platform": "twitter",
                        "username": "testuser",
                        "profile_url": "https://twitter.com/testuser",
                        "confidence": 0.8,
                    }
                ],
                "sources": ["test-source"],
            }
        ]

    pipeline._dispatch = mock_dispatch_with_handles

    request = EnrichmentRequest(linkedin_url="https://linkedin.com/in/test")
    job = await pipeline.run(request)

    assert job.status == JobStatus.completed.value
    assert len(job.dossier_payload.get("handles", [])) > 0

    pipeline._dispatch = original_dispatch


@pytest.mark.asyncio
async def test_job_with_emails_shows_completed(db: AsyncSession) -> None:
    """Job that finds emails should have status 'completed'."""
    pipeline = Pipeline(db)

    original_dispatch = pipeline._dispatch

    async def mock_dispatch_with_emails(request, sync_mode=False):
        return [{"emails": ["test@example.com"], "sources": ["test-source"]}]

    pipeline._dispatch = mock_dispatch_with_emails

    request = EnrichmentRequest(linkedin_url="https://linkedin.com/in/test")
    job = await pipeline.run(request)

    assert job.status == JobStatus.completed.value
    assert len(job.dossier_payload.get("emails", [])) > 0

    pipeline._dispatch = original_dispatch


@pytest.mark.asyncio
async def test_job_with_verified_emails_shows_completed(db: AsyncSession) -> None:
    """Job that finds verified emails should have status 'completed'."""
    pipeline = Pipeline(db)

    original_dispatch = pipeline._dispatch

    async def mock_dispatch_with_verified_emails(request, sync_mode=False):
        return [
            {
                "verified_emails": [
                    {
                        "value": "verified@example.com",
                        "status": "valid",
                        "confidence": 0.95,
                        "source": "test-source",
                    }
                ],
                "sources": ["test-source"],
            }
        ]

    pipeline._dispatch = mock_dispatch_with_verified_emails

    request = EnrichmentRequest(linkedin_url="https://linkedin.com/in/test")
    job = await pipeline.run(request)

    assert job.status == JobStatus.completed.value
    assert len(job.dossier_payload.get("verified_emails", [])) > 0

    pipeline._dispatch = original_dispatch


@pytest.mark.asyncio
async def test_job_with_business_shows_completed(db: AsyncSession) -> None:
    """Job that finds business profile should have status 'completed'."""
    pipeline = Pipeline(db)

    original_dispatch = pipeline._dispatch

    async def mock_dispatch_with_business(request, sync_mode=False):
        return [
            {
                "business": {
                    "name": "Test Company",
                    "address": "123 Test St",
                    "website": "https://test.com",
                    "rating": 4.5,
                    "phone": "+1234567890",
                },
                "sources": ["test-source"],
            }
        ]

    pipeline._dispatch = mock_dispatch_with_business

    request = EnrichmentRequest(business="Test Company")
    job = await pipeline.run(request)

    assert job.status == JobStatus.completed.value
    assert job.dossier_payload.get("business") is not None

    pipeline._dispatch = original_dispatch


@pytest.mark.asyncio
async def test_job_with_only_sources_shows_completed(db: AsyncSession) -> None:
    """Job that only has sources (no other data) should still show 'completed'."""
    pipeline = Pipeline(db)

    original_dispatch = pipeline._dispatch

    async def mock_dispatch_with_sources_only(request, sync_mode=False):
        return [{"sources": ["test-source"]}]

    pipeline._dispatch = mock_dispatch_with_sources_only

    request = EnrichmentRequest(linkedin_url="https://linkedin.com/in/test")
    job = await pipeline.run(request)

    assert job.status == JobStatus.completed.value
    assert len(job.dossier_payload.get("sources", [])) > 0

    pipeline._dispatch = original_dispatch


@pytest.mark.asyncio
async def test_multiple_enrichers_one_succeeds_shows_completed(db: AsyncSession) -> None:
    """If one enricher finds data and others don't, job should be 'completed'."""
    pipeline = Pipeline(db)

    original_dispatch = pipeline._dispatch

    async def mock_dispatch_mixed(request, sync_mode=False):
        return [
            {},  # First enricher found nothing
            {"sources": ["enricher2"], "emails": ["found@example.com"]},  # Second found data
            {},  # Third found nothing
        ]

    pipeline._dispatch = mock_dispatch_mixed

    request = EnrichmentRequest(linkedin_url="https://linkedin.com/in/test")
    job = await pipeline.run(request)

    assert job.status == JobStatus.completed.value
    assert len(job.dossier_payload.get("emails", [])) > 0

    pipeline._dispatch = original_dispatch


@pytest.mark.asyncio
async def test_suppressed_job_not_affected(db: AsyncSession) -> None:
    """Suppressed jobs should still show 'suppressed' status, not affected by data check."""
    pipeline = Pipeline(db)

    # First create an opt-out to trigger suppression
    from app.compliance.suppression import add_suppression

    await add_suppression(db, "https://linkedin.com/in/optedout", "user request")

    request = EnrichmentRequest(linkedin_url="https://linkedin.com/in/optedout")
    job = await pipeline.run(request)

    assert job.status == JobStatus.suppressed.value
