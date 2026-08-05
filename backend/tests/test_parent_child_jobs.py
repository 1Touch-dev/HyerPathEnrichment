"""Tests for parent-child job pattern in per_tier mode."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dossier import Dossier, PhotoAsset, SocialHandle
from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import JobStatus, RequestedTier
from app.enrichers.pipeline import Pipeline
from app.modules.enrichment.repository import JobRepository


@pytest.mark.asyncio
async def test_parent_child_job_creation(db: AsyncSession) -> None:
    """Test creating parent with tier1+234 children."""
    pipeline = Pipeline(db)

    request = EnrichmentRequest(
        linkedin_url="https://linkedin.com/in/test",
        username="testuser",
        requested_tiers=[RequestedTier.tier1, RequestedTier.tier2],
    )

    # Create parent
    parent = await pipeline.create_parent_job(request)
    assert parent.id.startswith("job_")
    assert parent.status == JobStatus.running.value
    assert parent.parent_job_id is None
    assert parent.child_job_ids == []

    # Create tier1 child
    tier1_child = await pipeline.create_child_job(parent, request, [RequestedTier.tier1.value])
    assert tier1_child.parent_job_id == parent.id
    assert tier1_child.tier_assignment == [RequestedTier.tier1.value]

    # Create tier234 child
    tier234_child = await pipeline.create_child_job(parent, request, [RequestedTier.tier2.value])
    assert tier234_child.parent_job_id == parent.id
    assert tier234_child.tier_assignment == [RequestedTier.tier2.value]

    # Refresh parent and check child_job_ids
    await db.commit()
    await db.refresh(parent)
    assert len(parent.child_job_ids) == 2
    assert tier1_child.id in parent.child_job_ids
    assert tier234_child.id in parent.child_job_ids


@pytest.mark.asyncio
async def test_get_children_and_parent(db: AsyncSession) -> None:
    """Test repository methods for parent-child relationships."""
    pipeline = Pipeline(db)
    jobs_repo = JobRepository(db)

    request = EnrichmentRequest(
        linkedin_url="https://linkedin.com/in/test",
        username="testuser",
        company="TestCorp",
        business="Test Business",
    )

    parent = await pipeline.create_parent_job(request)
    child1 = await pipeline.create_child_job(parent, request, ["tier1"])
    child2 = await pipeline.create_child_job(parent, request, ["tier2"])
    await db.commit()

    # Test get_children
    children = await jobs_repo.get_children(parent.id)
    assert len(children) == 2
    child_ids = {c.id for c in children}
    assert child1.id in child_ids
    assert child2.id in child_ids

    # Test get_parent
    parent_from_child = await jobs_repo.get_parent(child1)
    assert parent_from_child is not None
    assert parent_from_child.id == parent.id


@pytest.mark.asyncio
async def test_all_children_complete(db: AsyncSession) -> None:
    """Test checking if all child jobs are in terminal status."""
    pipeline = Pipeline(db)
    jobs_repo = JobRepository(db)

    request = EnrichmentRequest(
        linkedin_url="https://linkedin.com/in/test",
        username="testuser",
        company="TestCorp",
        business="Test Business",
    )

    parent = await pipeline.create_parent_job(request)
    child1 = await pipeline.create_child_job(parent, request, ["tier1"])
    child2 = await pipeline.create_child_job(parent, request, ["tier2"])
    await db.commit()

    # Initially, children are queued
    assert not await jobs_repo.all_children_complete(parent.id)

    # Mark one complete
    await jobs_repo.mark_status(child1, JobStatus.completed)
    assert not await jobs_repo.all_children_complete(parent.id)

    # Mark both complete
    await jobs_repo.mark_status(child2, JobStatus.completed)
    assert await jobs_repo.all_children_complete(parent.id)


@pytest.mark.asyncio
async def test_merge_child_dossiers_with_photo(db: AsyncSession) -> None:
    """Test merging child dossiers includes photo from tier1."""
    from datetime import UTC, datetime

    pipeline = Pipeline(db)

    # Create dossiers with different data
    tier1_dossier = Dossier(
        photo=PhotoAsset(
            source="linkedin-photo",
            asset_url="https://example.com/photo.jpg",
            captured_at=datetime.now(UTC),
            confidence=0.9,
        ),
        sources=["linkedin-photo"],
    )

    tier234_dossier = Dossier(
        handles=[
            SocialHandle(
                platform="Twitter",
                username="testuser",
                profile_url="https://twitter.com/testuser",
                confidence=0.85,
            )
        ],
        emails=["test@example.com"],
        sources=["Maigret", "theHarvester"],
    )

    # Merge
    merged = pipeline._merge_child_dossiers([tier1_dossier, tier234_dossier])

    # Verify photo is included
    assert merged.photo is not None
    assert merged.photo.source == "linkedin-photo"
    assert merged.photo.asset_url == "https://example.com/photo.jpg"

    # Verify other data is merged
    assert len(merged.handles) == 1
    assert merged.handles[0].username == "testuser"
    assert len(merged.emails) == 1
    assert "test@example.com" in merged.emails

    # Verify sources are combined
    assert "linkedin-photo" in merged.sources
    assert "Maigret" in merged.sources
    assert "theHarvester" in merged.sources


@pytest.mark.asyncio
async def test_merge_child_dossiers_deduplication(db: AsyncSession) -> None:
    """Test merging deduplicates handles, emails, etc."""
    pipeline = Pipeline(db)

    dossier1 = Dossier(
        handles=[
            SocialHandle(
                platform="Twitter",
                username="testuser",
                profile_url="https://twitter.com/testuser",
                confidence=0.85,
            )
        ],
        emails=["test@example.com", "test2@example.com"],
        sources=["Source1"],
    )

    dossier2 = Dossier(
        handles=[
            SocialHandle(
                platform="Twitter",
                username="testuser",  # Duplicate
                profile_url="https://twitter.com/testuser",
                confidence=0.80,
            ),
            SocialHandle(
                platform="GitHub",
                username="testuser",
                profile_url="https://github.com/testuser",
                confidence=0.90,
            ),
        ],
        emails=["test@example.com", "test3@example.com"],  # One duplicate
        sources=["Source1", "Source2"],  # One duplicate
    )

    merged = pipeline._merge_child_dossiers([dossier1, dossier2])

    # Handles deduplicated by (platform, username)
    assert len(merged.handles) == 2  # Twitter and GitHub
    platforms = {h.platform for h in merged.handles}
    assert "Twitter" in platforms
    assert "GitHub" in platforms

    # Emails deduplicated
    assert len(merged.emails) == 3
    assert "test@example.com" in merged.emails
    assert "test2@example.com" in merged.emails
    assert "test3@example.com" in merged.emails

    # Sources deduplicated
    assert len(merged.sources) == 2
    assert "Source1" in merged.sources
    assert "Source2" in merged.sources


@pytest.mark.asyncio
async def test_one_child_fails_parent_still_completes(db: AsyncSession) -> None:
    """If one child fails but another succeeds, parent still gets partial results."""
    pipeline = Pipeline(db)
    jobs_repo = JobRepository(db)

    request = EnrichmentRequest(
        linkedin_url="https://linkedin.com/in/test",
        username="testuser",
        company="TestCorp",
        business="Test Business",
    )

    parent = await pipeline.create_parent_job(request)
    child1 = await pipeline.create_child_job(parent, request, ["tier1"])
    child2 = await pipeline.create_child_job(parent, request, ["tier2"])
    await db.commit()

    # Child1 succeeds with data
    child1.dossier_payload = Dossier(
        emails=["success@example.com"],
        sources=["tier1-source"],
    ).model_dump(mode="json")
    await jobs_repo.mark_status(child1, JobStatus.completed)

    # Child2 fails
    await jobs_repo.mark_status(child2, JobStatus.failed)

    # Trigger merge
    await pipeline._try_merge_into_parent(child1)

    # Parent should be completed (at least one child succeeded)
    await db.refresh(parent)
    assert parent.status == JobStatus.completed.value

    # Parent should have partial results
    parent_dossier = Dossier.model_validate(parent.dossier_payload)
    assert "success@example.com" in parent_dossier.emails
    assert "tier1-source" in parent_dossier.sources


@pytest.mark.asyncio
async def test_all_children_fail_parent_fails(db: AsyncSession) -> None:
    """If all children fail, parent should be marked as failed."""
    pipeline = Pipeline(db)
    jobs_repo = JobRepository(db)

    request = EnrichmentRequest(
        linkedin_url="https://linkedin.com/in/test",
        username="testuser",
        company="TestCorp",
        business="Test Business",
    )

    parent = await pipeline.create_parent_job(request)
    child1 = await pipeline.create_child_job(parent, request, ["tier1"])
    child2 = await pipeline.create_child_job(parent, request, ["tier2"])
    await db.commit()

    # Both children fail
    await jobs_repo.mark_status(child1, JobStatus.failed)
    await jobs_repo.mark_status(child2, JobStatus.failed)

    # Trigger merge
    await pipeline._try_merge_into_parent(child1)

    # Parent should be failed
    await db.refresh(parent)
    assert parent.status == JobStatus.failed.value
