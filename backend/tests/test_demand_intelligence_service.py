"""Unit tests for app.modules.demand_intelligence.service/repository
(machine-2-parallel-tracks/02): compute_daily_snapshot aggregation,
get_top_countries_for_role read path, and classify_country_tier heuristic.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.demand_intelligence import repository, service
from app.modules.demand_intelligence.models import CountryDemandSnapshot
from app.modules.job_matching.models import JobPosting


async def _make_posting(db: AsyncSession, **overrides) -> JobPosting:
    fields = {
        "dedup_key": uuid.uuid4().hex,
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "Remote",
        "remote": False,
        "source": "linkedin",
        "sources_seen": ["linkedin"],
        "is_active": True,
        "country_iso2": "us",
    }
    fields.update(overrides)
    posting = JobPosting(**fields)
    db.add(posting)
    await db.commit()
    await db.refresh(posting)
    return posting


async def _make_snapshot(db: AsyncSession, **overrides: object) -> CountryDemandSnapshot:
    fields: dict[str, object] = {
        "snapshot_date": date(2026, 8, 25),
        "country_iso2": "us",
        "role_bucket": "backend engineer",
        "posting_count": 10,
        "remote_posting_count": 2,
        "avg_salary_min": 100_000,
        "avg_salary_max": 140_000,
    }
    fields.update(overrides)
    snapshot = CountryDemandSnapshot(**fields)
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


# ---------------------------------------------------------------------------
# compute_daily_snapshot
# ---------------------------------------------------------------------------


async def test_compute_daily_snapshot_aggregates_exact_counts(db: AsyncSession) -> None:
    role = f"unique role {uuid.uuid4().hex[:8]}"
    await _make_posting(db, title=role, country_iso2="us", remote=True)
    await _make_posting(db, title=role, country_iso2="us", remote=False)
    await _make_posting(db, title=role, country_iso2="in", remote=False)
    # Inactive posting must be excluded from the aggregate.
    await _make_posting(db, title=role, country_iso2="us", is_active=False)
    # NULL country_iso2 must be excluded (no country-demand signal).
    await _make_posting(db, title=role, country_iso2=None)

    target = date(2099, 1, 1)
    written = await service.compute_daily_snapshot(db, target_date=target)
    assert written >= 2

    snapshots = await repository.get_snapshots_for_role(db, role, target)
    by_country = {s.country_iso2: s for s in snapshots}

    assert by_country["us"].posting_count == 2
    assert by_country["us"].remote_posting_count == 1
    assert by_country["in"].posting_count == 1
    assert by_country["in"].remote_posting_count == 0


async def test_compute_daily_snapshot_bucket_is_lowercased_and_trimmed(
    db: AsyncSession,
) -> None:
    suffix = uuid.uuid4().hex[:8]
    await _make_posting(db, title=f"  Data Scientist {suffix}  ", country_iso2="de")
    await _make_posting(db, title=f"data scientist {suffix}", country_iso2="de")

    target = date(2099, 1, 2)
    await service.compute_daily_snapshot(db, target_date=target)

    snapshots = await repository.get_snapshots_for_role(db, f"data scientist {suffix}", target)
    # Both postings collapse into the same naive lowercased/trimmed bucket.
    assert len(snapshots) == 1
    assert snapshots[0].posting_count == 2


async def test_compute_daily_snapshot_is_idempotent_upsert_not_duplicate(
    db: AsyncSession,
) -> None:
    role = f"idempotent role {uuid.uuid4().hex[:8]}"
    await _make_posting(db, title=role, country_iso2="gb")

    target = date(2099, 1, 3)
    first = await service.compute_daily_snapshot(db, target_date=target)
    second = await service.compute_daily_snapshot(db, target_date=target)
    assert first == second

    snapshots = await repository.get_snapshots_for_role(db, role, target)
    assert len(snapshots) == 1
    assert snapshots[0].posting_count == 1


# ---------------------------------------------------------------------------
# get_top_countries_for_role
# ---------------------------------------------------------------------------


async def test_get_top_countries_for_role_orders_by_posting_count_desc(
    db: AsyncSession,
) -> None:
    role = f"ranked role {uuid.uuid4().hex[:8]}"
    snap_date = date(2099, 2, 1)
    await _make_snapshot(
        db, snapshot_date=snap_date, country_iso2="us", role_bucket=role, posting_count=5
    )
    await _make_snapshot(
        db, snapshot_date=snap_date, country_iso2="in", role_bucket=role, posting_count=50
    )
    await _make_snapshot(
        db, snapshot_date=snap_date, country_iso2="ie", role_bucket=role, posting_count=20
    )

    results = await service.get_top_countries_for_role(db, role, limit=10)
    assert [s.country_iso2 for s in results] == ["in", "ie", "us"]


async def test_get_top_countries_for_role_respects_limit(db: AsyncSession) -> None:
    role = f"limited role {uuid.uuid4().hex[:8]}"
    snap_date = date(2099, 2, 2)
    for i, country in enumerate(["us", "gb", "in", "ae", "sg"]):
        await _make_snapshot(
            db, snapshot_date=snap_date, country_iso2=country, role_bucket=role, posting_count=i + 1
        )

    results = await service.get_top_countries_for_role(db, role, limit=2)
    assert len(results) == 2


async def test_get_top_countries_for_role_case_insensitive_substring_match(
    db: AsyncSession,
) -> None:
    unique = uuid.uuid4().hex[:8]
    role_bucket = f"senior backend engineer {unique}"
    snap_date = date(2099, 2, 3)
    await _make_snapshot(
        db, snapshot_date=snap_date, country_iso2="us", role_bucket=role_bucket, posting_count=3
    )

    results = await service.get_top_countries_for_role(db, f"BACKEND ENGINEER {unique}".upper())
    assert len(results) == 1
    assert results[0].country_iso2 == "us"


async def test_get_top_countries_for_role_no_match_returns_empty(db: AsyncSession) -> None:
    results = await service.get_top_countries_for_role(db, f"no-such-role-{uuid.uuid4().hex}")
    assert results == []


# ---------------------------------------------------------------------------
# classify_country_tier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("country_iso2", ["us", "gb", "de", "nl", "fr", "ca"])
async def test_classify_country_tier_fixed_tier1_countries_always_tier1(
    country_iso2: str,
) -> None:
    """USA/major-Europe/Canada always classify tier_1 regardless of this
    particular role query's own posting_count -- even when ranked last."""
    snapshot = CountryDemandSnapshot(
        snapshot_date=date(2026, 1, 1),
        country_iso2=country_iso2,
        role_bucket="niche role",
        posting_count=1,
    )
    other_snapshots = [
        CountryDemandSnapshot(
            snapshot_date=date(2026, 1, 1),
            country_iso2="xx",
            role_bucket="niche role",
            posting_count=1000,
        ),
        snapshot,
    ]
    tier = await service.classify_country_tier(snapshot, other_snapshots)
    assert tier == "tier_1"


async def test_classify_country_tier_buckets_into_thirds() -> None:
    """A synthetic 9-snapshot set (non-Tier-1 country codes) must bucket into
    top/middle/bottom thirds by posting_count."""
    snapshots = [
        CountryDemandSnapshot(
            id=uuid.uuid4(),
            snapshot_date=date(2026, 1, 1),
            country_iso2="xx",
            role_bucket="role",
            posting_count=count,
        )
        for count in [90, 80, 70, 50, 40, 30, 10, 5, 1]
    ]

    top = await service.classify_country_tier(snapshots[0], snapshots)
    middle = await service.classify_country_tier(snapshots[4], snapshots)
    bottom = await service.classify_country_tier(snapshots[-1], snapshots)

    assert top == "tier_1"
    assert middle == "tier_2"
    assert bottom == "tier_3"


async def test_classify_country_tier_empty_comparison_set_defaults_to_tier3() -> None:
    snapshot = CountryDemandSnapshot(
        snapshot_date=date(2026, 1, 1), country_iso2="xx", role_bucket="role", posting_count=5
    )
    tier = await service.classify_country_tier(snapshot, [])
    assert tier == "tier_3"
