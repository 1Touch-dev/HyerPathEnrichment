"""Job-match analytics: aggregate queries over job_matching's existing tables.
See phase2_admin_module.md §3 — corrects docs/admin-module-research.md's stale
'0 days buildable' claim. Read-only against job_postings/job_matches; never
writes to either table, matching job_swipe's existing read-only-dependency
convention on the same tables."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.cache import cached_aggregate, utcnow
from app.modules.admin.schemas import JobMatchAnalyticsResponse
from app.modules.job_matching.models import JobMatch, JobPosting


async def _compute_job_match_analytics(db: AsyncSession) -> JobMatchAnalyticsResponse:
    total_postings = (await db.execute(select(func.count()).select_from(JobPosting))).scalar_one()
    total_matches = (await db.execute(select(func.count()).select_from(JobMatch))).scalar_one()

    by_source_rows = await db.execute(
        select(JobPosting.source, func.count()).group_by(JobPosting.source)
    )
    postings_by_source = {row[0]: row[1] for row in by_source_rows.all()}

    top_companies_rows = await db.execute(
        select(JobPosting.company, func.count().label("count"))
        .group_by(JobPosting.company)
        .order_by(func.count().desc())
        .limit(10)
    )
    top_companies = [{"company": row[0], "count": row[1]} for row in top_companies_rows.all()]

    avg_row = (
        await db.execute(
            select(
                func.avg(JobPosting.salary_min),
                func.avg(JobPosting.salary_max),
            )
        )
    ).one()
    avg_score_row = (await db.execute(select(func.avg(JobMatch.overall_score)))).scalar_one()

    return JobMatchAnalyticsResponse(
        total_postings=total_postings,
        total_matches=total_matches,
        postings_by_source=postings_by_source,
        top_companies=top_companies,
        avg_salary_min=float(avg_row[0]) if avg_row[0] is not None else None,
        avg_salary_max=float(avg_row[1]) if avg_row[1] is not None else None,
        avg_overall_score=float(avg_score_row) if avg_score_row is not None else None,
        computed_at=utcnow(),
        cache_hit=False,
    )


async def get_job_match_analytics(
    db: AsyncSession, *, refresh: bool = False
) -> JobMatchAnalyticsResponse:
    result, cache_hit = await cached_aggregate(
        "job_match_analytics",
        JobMatchAnalyticsResponse,
        lambda: _compute_job_match_analytics(db),
        refresh=refresh,
    )
    result.cache_hit = cache_hit
    return result
