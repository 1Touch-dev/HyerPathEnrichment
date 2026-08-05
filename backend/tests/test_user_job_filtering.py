"""Test user-specific job filtering and ownership verification."""

from __future__ import annotations

import pytest
from uuid import uuid4

from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import JobStatus
from app.modules.enrichment.repository import JobRepository
from app.modules.enrichment.service import EnrichmentService
from app.enrichers.pipeline import Pipeline


@pytest.mark.asyncio
async def test_list_jobs_filters_by_user_id(db):
    """Test that list_jobs only returns jobs for the specified user."""
    repo = JobRepository(db)

    # Create users
    user1_id = uuid4()
    user2_id = uuid4()

    # Create jobs for user 1
    request = EnrichmentRequest(username="testuser", requested_tiers=["tier2"])
    await repo.create(request, JobStatus.completed, user_id=user1_id)
    await repo.create(request, JobStatus.completed, user_id=user1_id)

    # Create jobs for user 2
    await repo.create(request, JobStatus.completed, user_id=user2_id)
    await repo.create(request, JobStatus.completed, user_id=user2_id)

    # Create job with no user
    await repo.create(request, JobStatus.completed, user_id=None)

    await db.commit()

    # List jobs for user 1
    user1_jobs, user1_total = await repo.list(limit=10, offset=0, user_id=user1_id)
    assert user1_total == 2
    assert len(user1_jobs) == 2
    assert all(job.user_id == user1_id for job in user1_jobs)

    # List jobs for user 2
    user2_jobs, user2_total = await repo.list(limit=10, offset=0, user_id=user2_id)
    assert user2_total == 2
    assert len(user2_jobs) == 2
    assert all(job.user_id == user2_id for job in user2_jobs)

    # List all jobs (no filter)
    all_jobs, all_total = await repo.list(limit=10, offset=0, user_id=None)
    assert all_total == 5
    assert len(all_jobs) == 5


@pytest.mark.asyncio
async def test_get_job_ownership_verification(db):
    """Test that get_job verifies ownership."""
    service = EnrichmentService(db)
    pipeline = Pipeline(db)

    # Create users
    user1_id = uuid4()
    user2_id = uuid4()

    # Create job for user 1
    request = EnrichmentRequest(username="testuser", requested_tiers=[])
    job = await pipeline.create_queued_job(request, user_id=user1_id)

    # User 1 can access their own job
    result = await service.get_job(job.id, user_id=user1_id)
    assert result.id == job.id

    # User 2 cannot access user 1's job
    from app.core.errors import NotFoundError

    with pytest.raises(NotFoundError):
        await service.get_job(job.id, user_id=user2_id)


@pytest.mark.asyncio
async def test_child_jobs_inherit_parent_user_id(db):
    """Test that child jobs inherit the parent's user_id."""
    repo = JobRepository(db)

    user_id = uuid4()
    request = EnrichmentRequest(username="testuser", requested_tiers=[])

    # Create parent job with user_id
    parent = await repo.create(request, JobStatus.running, user_id=user_id)
    await db.flush()

    # Create child job
    child = await repo.create_child_job(parent, request, ["tier1"])
    await db.commit()

    # Verify child inherited parent's user_id
    assert child.user_id == user_id
    assert child.parent_job_id == parent.id


@pytest.mark.asyncio
async def test_pagination_with_user_filter(db):
    """Test pagination works correctly with user filtering."""
    repo = JobRepository(db)

    user_id = uuid4()
    request = EnrichmentRequest(username="testuser", requested_tiers=[])

    # Create 25 jobs for user
    for _ in range(25):
        await repo.create(request, JobStatus.completed, user_id=user_id)

    await db.commit()

    # First page
    page1_jobs, total = await repo.list(limit=10, offset=0, user_id=user_id)
    assert len(page1_jobs) == 10
    assert total == 25

    # Second page
    page2_jobs, _ = await repo.list(limit=10, offset=10, user_id=user_id)
    assert len(page2_jobs) == 10

    # Third page
    page3_jobs, _ = await repo.list(limit=10, offset=20, user_id=user_id)
    assert len(page3_jobs) == 5

    # No overlap between pages
    page1_ids = {job.id for job in page1_jobs}
    page2_ids = {job.id for job in page2_jobs}
    page3_ids = {job.id for job in page3_jobs}

    assert len(page1_ids & page2_ids) == 0
    assert len(page2_ids & page3_ids) == 0
    assert len(page1_ids & page3_ids) == 0


@pytest.mark.asyncio
async def test_internal_jobs_excluded_from_user_list(db):
    """Test that internal jobs are excluded from user job lists."""
    repo = JobRepository(db)

    user_id = uuid4()
    request = EnrichmentRequest(username="testuser", requested_tiers=[])

    # Create regular job
    parent = await repo.create(request, JobStatus.running, user_id=user_id)
    await db.flush()

    # Create internal child job
    child = await repo.create_child_job(parent, request, ["tier1"])
    await db.commit()

    # List should only show parent (child is internal)
    jobs, total = await repo.list(limit=10, offset=0, user_id=user_id)
    assert total == 1
    assert len(jobs) == 1
    assert jobs[0].id == parent.id
    assert jobs[0].is_internal is False

    # Child should not appear
    assert child.is_internal is True
    assert child.id not in [job.id for job in jobs]
