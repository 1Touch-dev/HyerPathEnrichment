"""Country-demand aggregation (write path) + top-countries/tiering (read path).

Two responsibilities per machine-2-parallel-tracks/02:
1. ``compute_daily_snapshot`` — periodic aggregation of ``job_postings`` into
   ``CountryDemandSnapshot`` rows (one per (country_iso2, role_bucket) pair).
2. ``get_top_countries_for_role`` / ``classify_country_tier`` — the read path
   consumed by this module's own router and (per the doc's "India/Middle East
   resume-personalization consumer" section) a future resume-tailoring chunk.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.demand_intelligence import repository
from app.modules.demand_intelligence.models import CountryDemandSnapshot

# Tier 1 — high-volume, high-competition markets. Always tier_1 regardless of a
# particular role query's own posting_count distribution, since USA/Europe/
# Canada's Tier-1 status reflects overall market maturity, not one role
# bucket's snapshot (see 02-country-demand-intelligence.md's tiered
# market-research methodology).
_TIER_1_COUNTRIES: frozenset[str] = frozenset(
    {
        "us",  # USA
        "gb",  # UK
        "de",  # Germany
        "nl",  # Netherlands
        "fr",  # France
        "ca",  # Canada
    }
)


async def compute_daily_snapshot(db: AsyncSession, target_date: date | None = None) -> int:
    """Aggregate active job_postings by (country_iso2, role_bucket) for ``target_date``
    (default: today, UTC) and upsert one CountryDemandSnapshot row per pair.

    ``role_bucket`` is a naive lowercased/trimmed bucket of ``JobPosting.title`` —
    deliberately not an NLP-normalized title grouping; a naive bucket is
    documented here as acceptable for this chunk's scope, per the doc's
    "do not build an NLP title-normalization system" instruction.

    Returns the number of snapshot rows written, for the calling worker job's logging.
    """
    snapshot_date = target_date or datetime.now(UTC).date()
    rows = await repository.aggregate_active_postings_by_country_and_role(db)

    written = 0
    for row in rows:
        if not row.country_iso2 or not row.role_bucket:
            continue
        await repository.upsert_snapshot(
            db,
            snapshot_date=snapshot_date,
            country_iso2=row.country_iso2,
            role_bucket=row.role_bucket,
            posting_count=row.posting_count,
            remote_posting_count=row.remote_posting_count,
            avg_salary_min=int(row.avg_salary_min) if row.avg_salary_min is not None else None,
            avg_salary_max=int(row.avg_salary_max) if row.avg_salary_max is not None else None,
        )
        written += 1

    return written


async def get_top_countries_for_role(
    db: AsyncSession, role_query: str, limit: int = 10
) -> list[CountryDemandSnapshot]:
    """Read path: most recent snapshot_date, role_bucket matching ``role_query``
    (case-insensitive substring), ordered by posting_count descending, top ``limit``."""
    latest_date = await repository.get_latest_snapshot_date_for_role(db, role_query)
    if latest_date is None:
        return []
    snapshots = await repository.get_snapshots_for_role(db, role_query, latest_date)
    return snapshots[:limit]


async def classify_country_tier(
    snapshot: CountryDemandSnapshot,
    all_snapshots_for_role: list[CountryDemandSnapshot],
) -> Literal["tier_1", "tier_2", "tier_3"]:
    """Derived view over a role query's full snapshot set — not a persisted
    classification. Fixed Tier-1 countries (USA/Europe/Canada) always classify
    ``tier_1``. Everything else is bucketed into top/middle/bottom-thirds by
    ``posting_count`` relative to ``all_snapshots_for_role`` — a simple,
    documented heuristic sufficient for this chunk's scope (see module docstring
    and 02-country-demand-intelligence.md's tiered market-research methodology;
    do not build a more sophisticated competition model than this data supports).
    """
    if snapshot.country_iso2.lower() in _TIER_1_COUNTRIES:
        return "tier_1"

    if not all_snapshots_for_role:
        return "tier_3"

    ordered = sorted(all_snapshots_for_role, key=lambda s: s.posting_count, reverse=True)
    total = len(ordered)
    rank = next(
        (i for i, s in enumerate(ordered) if s is snapshot),
        None,
    )
    if rank is None:
        # Snapshot not present (by identity) in the comparison set — fall back to
        # comparing by posting_count value directly against the set's own thirds
        # boundaries.
        rank = sum(1 for s in ordered if s.posting_count > snapshot.posting_count)

    third = max(total // 3, 1)
    if rank < third:
        return "tier_1"
    if rank < 2 * third:
        return "tier_2"
    return "tier_3"
