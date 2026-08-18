"""Job-match analytics — the §3 ground-truth correction (phase2_admin_module.md
§9.7). Verifies the endpoint reads real Module 1 tables and never writes to
them."""

from __future__ import annotations

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


async def test_analytics_reads_job_postings_and_matches(
    db_session, seeded_job_postings, mock_redis
):
    from app.modules.admin.analytics import get_job_match_analytics

    result = await get_job_match_analytics(db_session)
    # `job_postings`/`job_matches` are shared, session-scoped tables across the
    # whole test run (other test files add their own rows) — assert this
    # fixture's rows are counted (>=), not that the table contains nothing
    # else, to stay correct regardless of test execution order.
    assert result.total_postings >= len(seeded_job_postings)
    assert result.cache_hit is False  # first call, cold cache


async def test_analytics_second_call_hits_cache(db_session, seeded_job_postings, mock_redis):
    from app.modules.admin.analytics import get_job_match_analytics

    await get_job_match_analytics(db_session)
    result = await get_job_match_analytics(db_session)
    assert result.cache_hit is True


async def test_analytics_refresh_bypasses_cache(db_session, seeded_job_postings, mock_redis):
    from app.modules.admin.analytics import get_job_match_analytics

    await get_job_match_analytics(db_session)
    result = await get_job_match_analytics(db_session, refresh=True)
    assert result.cache_hit is False


async def test_analytics_never_writes_to_job_matching_tables(
    db_session, seeded_job_postings, mock_redis
):
    from app.modules.admin.analytics import get_job_match_analytics
    from app.modules.job_matching.models import JobPosting

    before_count = len((await db_session.execute(select(JobPosting))).all())
    await get_job_match_analytics(db_session)
    after_count = len((await db_session.execute(select(JobPosting))).all())
    assert before_count == after_count


async def test_analytics_aggregates_by_source_and_company(
    db_session, seeded_job_postings, mock_redis
):
    """`postings_by_source` groups over ALL rows (not top-N), so — unlike
    `top_companies`, which is limited to the top 10 and could be pushed out
    by other test files' data in a full-suite run — its per-key counts for
    this fixture's own uuid-suffixed source name are safe to assert exactly,
    regardless of what else exists in the shared, session-scoped table."""
    from app.modules.admin.analytics import get_job_match_analytics

    result = await get_job_match_analytics(db_session)

    expected_by_source: dict[str, int] = {}
    for posting in seeded_job_postings:
        expected_by_source[posting.source] = expected_by_source.get(posting.source, 0) + 1

    for source, count in expected_by_source.items():
        assert result.postings_by_source[source] == count
    assert result.avg_salary_min is not None
    assert result.avg_overall_score is not None
