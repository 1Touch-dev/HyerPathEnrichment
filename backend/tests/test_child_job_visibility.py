"""Test that child jobs are hidden from users"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import JobStatus, RequestedTier
from app.modules.enrichment.repository import JobRepository
from app.modules.enrichment.service import EnrichmentService


@pytest.mark.asyncio
async def test_list_jobs_excludes_child_jobs(db: AsyncSession):
    """Test that child jobs are excluded from list by default"""
    repo = JobRepository(db)

    # Get initial count (other tests in the shared session-scoped DB may
    # have already committed external jobs, so we compare against a
    # baseline rather than asserting an absolute count).
    _, initial_total = await repo.list(limit=100, offset=0)

    # Create a parent job
    parent_request = EnrichmentRequest(
        linkedin_url="https://linkedin.com/in/test",
        username="testuser",
        requested_tiers=[RequestedTier.tier1, RequestedTier.tier2],
    )
    parent_job = await repo.create(parent_request, JobStatus.queued)

    # Create two child jobs
    child1 = await repo.create_child_job(parent_job, parent_request, [RequestedTier.tier1.value])
    child2 = await repo.create_child_job(parent_job, parent_request, [RequestedTier.tier2.value])

    await db.commit()

    # List jobs (default: exclude internal)
    jobs, total = await repo.list(limit=100, offset=0)

    # Should only contain the new parent job (children remain hidden)
    assert total == initial_total + 1
    new_job_ids = {job.id for job in jobs}
    assert parent_job.id in new_job_ids
    assert child1.id not in new_job_ids
    assert child2.id not in new_job_ids
    matched = next(job for job in jobs if job.id == parent_job.id)
    assert matched.is_internal is False

    # Verify child jobs are marked as internal
    assert child1.is_internal is True
    assert child2.is_internal is True


@pytest.mark.asyncio
async def test_list_jobs_includes_internal_when_requested(db: AsyncSession):
    """Test that internal jobs can be explicitly included"""
    repo = JobRepository(db)

    # Get initial counts
    _, initial_all = await repo.list(limit=100, offset=0, include_internal=True)
    _, initial_external = await repo.list(limit=100, offset=0, include_internal=False)

    # Create a parent job with children
    parent_request = EnrichmentRequest(
        linkedin_url="https://linkedin.com/in/test",
        username="testuser",
        requested_tiers=[RequestedTier.tier1, RequestedTier.tier2],
    )
    parent_job = await repo.create(parent_request, JobStatus.queued)
    await repo.create_child_job(parent_job, parent_request, [RequestedTier.tier1.value])
    await repo.create_child_job(parent_job, parent_request, [RequestedTier.tier2.value])

    await db.commit()

    # List jobs with include_internal=True
    _jobs, total = await repo.list(limit=100, offset=0, include_internal=True)

    # Should contain 3 more jobs than before (1 parent + 2 children)
    assert total == initial_all + 3

    # List jobs with include_internal=False
    _jobs_external, total_external = await repo.list(limit=100, offset=0, include_internal=False)

    # Should contain 1 more job than before (just parent)
    assert total_external == initial_external + 1


@pytest.mark.asyncio
async def test_get_child_job_returns_parent(db: AsyncSession):
    """Test that getting a child job returns the parent job instead"""
    service = EnrichmentService(db)

    # Create parent job with child
    parent_request = EnrichmentRequest(
        linkedin_url="https://linkedin.com/in/test",
        username="testuser",
        requested_tiers=[RequestedTier.tier1, RequestedTier.tier2],
    )
    parent_job = await service.pipeline.create_parent_job(parent_request)
    child_job = await service.pipeline.create_child_job(
        parent_job, parent_request, [RequestedTier.tier1.value]
    )

    await db.commit()

    # Get child job via service
    response = await service.get_job(child_job.id)

    # Should return parent job, not child
    assert response.id == parent_job.id
    assert response.id != child_job.id


@pytest.mark.asyncio
async def test_get_parent_job_returns_parent(db: AsyncSession):
    """Test that getting a parent job returns itself"""
    service = EnrichmentService(db)

    # Create parent job
    parent_request = EnrichmentRequest(
        linkedin_url="https://linkedin.com/in/test",
        username="testuser",
        requested_tiers=[RequestedTier.tier1, RequestedTier.tier2],
    )
    parent_job = await service.pipeline.create_parent_job(parent_request)

    await db.commit()

    # Get parent job
    response = await service.get_job(parent_job.id)

    # Should return the same parent job
    assert response.id == parent_job.id


@pytest.mark.asyncio
async def test_workers_can_access_child_jobs(db: AsyncSession):
    """Test that workers can still access child jobs for processing"""
    repo = JobRepository(db)

    # Create parent with children
    parent_request = EnrichmentRequest(
        linkedin_url="https://linkedin.com/in/test",
        username="testuser",
        requested_tiers=[RequestedTier.tier1, RequestedTier.tier2],
    )
    parent_job = await repo.create(parent_request, JobStatus.queued)
    child1 = await repo.create_child_job(parent_job, parent_request, [RequestedTier.tier1.value])
    child2 = await repo.create_child_job(parent_job, parent_request, [RequestedTier.tier2.value])

    await db.commit()

    # Workers should be able to get child jobs directly
    fetched_child1 = await repo.get(child1.id)
    fetched_child2 = await repo.get(child2.id)

    assert fetched_child1 is not None
    assert fetched_child2 is not None
    assert fetched_child1.id == child1.id
    assert fetched_child2.id == child2.id

    # Workers should be able to list children of a parent
    children = await repo.get_children(parent_job.id)
    assert len(children) == 2
    child_ids = {child.id for child in children}
    assert child1.id in child_ids
    assert child2.id in child_ids


@pytest.mark.asyncio
async def test_child_job_has_correct_flags(db: AsyncSession):
    """Test that child jobs have all required flags set correctly"""
    repo = JobRepository(db)

    # Create parent with child
    parent_request = EnrichmentRequest(
        linkedin_url="https://linkedin.com/in/test",
        username="testuser",
        requested_tiers=[RequestedTier.tier1, RequestedTier.tier2],
    )
    parent_job = await repo.create(parent_request, JobStatus.queued)
    child_job = await repo.create_child_job(parent_job, parent_request, [RequestedTier.tier1.value])

    await db.commit()

    # Verify child job flags
    assert child_job.is_internal is True
    assert child_job.parent_job_id == parent_job.id
    assert child_job.tier_assignment == [RequestedTier.tier1.value]

    # Verify parent job flags
    assert parent_job.is_internal is False
    assert parent_job.parent_job_id is None
    assert child_job.id in parent_job.child_job_ids


@pytest.mark.asyncio
async def test_list_jobs_pagination_excludes_child_jobs(db: AsyncSession):
    """Test that pagination counts exclude child jobs"""
    repo = JobRepository(db)

    # Get initial count
    _, initial_count = await repo.list(limit=100, offset=0, include_internal=False)

    # Create 3 parent jobs with children
    for i in range(3):
        parent_request = EnrichmentRequest(
            linkedin_url=f"https://linkedin.com/in/test{i}",
            username=f"testuser{i}",
            requested_tiers=[RequestedTier.tier1, RequestedTier.tier2],
        )
        parent_job = await repo.create(parent_request, JobStatus.queued)
        await repo.create_child_job(parent_job, parent_request, [RequestedTier.tier1.value])
        await repo.create_child_job(parent_job, parent_request, [RequestedTier.tier2.value])

    await db.commit()

    # Total should be 3 more than before (parents only), not +9 (parents + children)
    jobs, total = await repo.list(limit=100, offset=0)
    assert total == initial_count + 3
    assert all(not job.is_internal for job in jobs)
