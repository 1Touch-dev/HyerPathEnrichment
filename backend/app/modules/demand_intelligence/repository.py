"""Data-access layer for country-demand snapshots. Workers import this, never
service.py directly for DB access outside this module (consistent with the
job_matching/manual_jobs "workers import repository" convention).
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.demand_intelligence.models import CountryDemandSnapshot
from app.modules.job_matching.models import JobPosting


class AggregatedRoleCountryRow(NamedTuple):
    country_iso2: str
    role_bucket: str
    posting_count: int
    remote_posting_count: int
    avg_salary_min: float | None
    avg_salary_max: float | None


async def aggregate_active_postings_by_country_and_role(
    db: AsyncSession,
) -> list[AggregatedRoleCountryRow]:
    """Aggregate currently-active job_postings by (country_iso2, role_bucket).

    ``role_bucket`` is a naive lowercased/trimmed bucket of ``JobPosting.title`` —
    not an NLP-normalized title (out of scope for this chunk, see service.py's
    ``compute_daily_snapshot`` docstring). Postings with no resolved
    ``country_iso2`` (NULL — scraped before this column existed, or country
    could not be determined) are excluded; they carry no country-demand signal.
    """
    role_bucket_expr = func.lower(func.trim(JobPosting.title))
    stmt = (
        select(
            JobPosting.country_iso2,
            role_bucket_expr.label("role_bucket"),
            func.count(JobPosting.id).label("posting_count"),
            func.sum(func.cast(JobPosting.remote, Integer)).label("remote_posting_count"),
            func.avg(JobPosting.salary_min).label("avg_salary_min"),
            func.avg(JobPosting.salary_max).label("avg_salary_max"),
        )
        .where(JobPosting.is_active.is_(True))
        .where(JobPosting.country_iso2.is_not(None))
        .group_by(JobPosting.country_iso2, role_bucket_expr)
    )
    result = await db.execute(stmt)
    rows: list[AggregatedRoleCountryRow] = []
    for row in result.all():
        rows.append(
            AggregatedRoleCountryRow(
                country_iso2=row.country_iso2,
                role_bucket=row.role_bucket,
                posting_count=int(row.posting_count or 0),
                remote_posting_count=int(row.remote_posting_count or 0),
                avg_salary_min=row.avg_salary_min,
                avg_salary_max=row.avg_salary_max,
            )
        )
    return rows


async def upsert_snapshot(
    db: AsyncSession,
    *,
    snapshot_date: date,
    country_iso2: str,
    role_bucket: str,
    posting_count: int,
    remote_posting_count: int,
    avg_salary_min: int | None,
    avg_salary_max: int | None,
) -> CountryDemandSnapshot:
    """Insert or refresh the one row for (snapshot_date, country_iso2, role_bucket) —
    matches the unique constraint added in this chunk's migration, so re-running the
    aggregation job for the same day upserts rather than duplicates."""
    result = await db.execute(
        select(CountryDemandSnapshot).where(
            CountryDemandSnapshot.snapshot_date == snapshot_date,
            CountryDemandSnapshot.country_iso2 == country_iso2,
            CountryDemandSnapshot.role_bucket == role_bucket,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.posting_count = posting_count
        existing.remote_posting_count = remote_posting_count
        existing.avg_salary_min = avg_salary_min
        existing.avg_salary_max = avg_salary_max
        await db.commit()
        await db.refresh(existing)
        return existing

    snapshot = CountryDemandSnapshot(
        snapshot_date=snapshot_date,
        country_iso2=country_iso2,
        role_bucket=role_bucket,
        posting_count=posting_count,
        remote_posting_count=remote_posting_count,
        avg_salary_min=avg_salary_min,
        avg_salary_max=avg_salary_max,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def get_latest_snapshot_date_for_role(db: AsyncSession, role_query: str) -> date | None:
    """Most recent snapshot_date with at least one row whose role_bucket matches
    ``role_query`` as a case-insensitive substring."""
    pattern = f"%{role_query.strip().lower()}%"
    result = await db.execute(
        select(func.max(CountryDemandSnapshot.snapshot_date)).where(
            func.lower(CountryDemandSnapshot.role_bucket).like(pattern)
        )
    )
    return result.scalar_one_or_none()


async def get_snapshots_for_role(
    db: AsyncSession, role_query: str, snapshot_date: date
) -> list[CountryDemandSnapshot]:
    """All snapshot rows for ``snapshot_date`` whose role_bucket case-insensitively
    matches ``role_query`` as a substring — the full set (no limit), used both as
    the source for the top-N read path and as the tiering basis for
    ``classify_country_tier`` (which needs the whole role's distribution, not just
    the top N, to bucket into thirds)."""
    pattern = f"%{role_query.strip().lower()}%"
    result = await db.execute(
        select(CountryDemandSnapshot)
        .where(CountryDemandSnapshot.snapshot_date == snapshot_date)
        .where(func.lower(CountryDemandSnapshot.role_bucket).like(pattern))
        .order_by(CountryDemandSnapshot.posting_count.desc())
    )
    return list(result.scalars().all())
