"""Repository-layer tests for the application tracker (Module 4, Module C).

Mirrors the pattern in test_job_matching_repository.py: `test_user`/`second_test_user`
fixtures are defined locally since there's no shared user fixture in conftest.py, and
committed rows persist across tests in the same DB (no per-test transaction rollback),
so assertions scope explicitly to the fixture's own user/postings rather than assuming
an empty table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.password import hash_password
from app.modules.application_tracker import repository
from app.modules.job_matching import repository as job_matching_repository
from app.modules.job_matching.models import JobMatch, JobPosting
from app.modules.manual_jobs.models import ManualJobEntry


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    user = User(
        email=f"tracker-primary-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Primary",
        last_name="Candidate",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def second_test_user(db: AsyncSession) -> User:
    user = User(
        email=f"tracker-secondary-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Secondary",
        last_name="Candidate",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_posting(db: AsyncSession, **overrides) -> JobPosting:
    fields = {
        "dedup_key": uuid.uuid4().hex,
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "Remote",
        "remote": True,
        "source": "linkedin",
        "sources_seen": ["linkedin"],
        "is_active": True,
    }
    fields.update(overrides)
    posting = JobPosting(**fields)
    db.add(posting)
    await db.commit()
    await db.refresh(posting)
    return posting


async def _make_match(
    db: AsyncSession, user_id: uuid.UUID, posting: JobPosting, **overrides
) -> JobMatch:
    fields = {
        "user_id": user_id,
        "job_posting_id": posting.id,
        "similarity_score": 0.5,
        "rule_score": 0.5,
        "overall_score": 50.0,
        "score_breakdown": {},
    }
    fields.update(overrides)
    match = JobMatch(**fields)
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


async def _make_manual_entry(db: AsyncSession, user_id: uuid.UUID, **overrides) -> ManualJobEntry:
    fields = {
        "user_id": user_id,
        "title": "Self-Sourced Role",
        "company": "Referral Co",
        "location": "Remote",
    }
    fields.update(overrides)
    entry = ManualJobEntry(**fields)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def _make_manual_match(
    db: AsyncSession, user_id: uuid.UUID, entry: ManualJobEntry, **overrides
) -> JobMatch:
    fields = {
        "user_id": user_id,
        "job_posting_id": None,
        "manual_job_entry_id": entry.id,
        "similarity_score": 0.0,
        "rule_score": 0.0,
        "overall_score": 0.0,
        "score_breakdown": {},
        "application_status": "new",
    }
    fields.update(overrides)
    match = JobMatch(**fields)
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


class TestListTrackedMatchesStatusFilter:
    async def test_filters_by_status(self, db: AsyncSession, test_user: User):
        posting_new = await _make_posting(db)
        posting_applied = await _make_posting(db)
        match_new = await _make_match(db, test_user.id, posting_new)
        match_applied = await _make_match(db, test_user.id, posting_applied)
        await repository.update_status(db, match_applied.id, test_user.id, "applied")

        rows, total = await repository.list_tracked_matches(
            db, test_user.id, status="applied", sort="newest", limit=20, offset=0
        )

        assert total == 1
        assert len(rows) == 1
        assert rows[0][0].id == match_applied.id
        assert rows[0][0].id != match_new.id

    async def test_no_status_filter_returns_all(self, db: AsyncSession, test_user: User):
        posting1 = await _make_posting(db)
        posting2 = await _make_posting(db)
        await _make_match(db, test_user.id, posting1)
        await _make_match(db, test_user.id, posting2)

        rows, total = await repository.list_tracked_matches(
            db, test_user.id, status=None, sort="newest", limit=20, offset=0
        )

        assert total == 2
        assert len(rows) == 2


class TestListTrackedMatchesSortOrders:
    async def test_sort_newest_orders_by_created_at_descending(
        self, db: AsyncSession, test_user: User
    ):
        posting1 = await _make_posting(db)
        posting2 = await _make_posting(db)
        posting3 = await _make_posting(db)
        older = await _make_match(
            db, test_user.id, posting1, created_at=datetime.now(UTC) - timedelta(hours=2)
        )
        newer = await _make_match(
            db, test_user.id, posting2, created_at=datetime.now(UTC) - timedelta(hours=1)
        )
        newest = await _make_match(db, test_user.id, posting3, created_at=datetime.now(UTC))

        rows, _ = await repository.list_tracked_matches(
            db, test_user.id, status=None, sort="newest", limit=20, offset=0
        )
        result_ids = [m.id for m, _ in rows]

        assert result_ids == [newest.id, newer.id, older.id]

    async def test_sort_oldest_orders_by_created_at_ascending(
        self, db: AsyncSession, test_user: User
    ):
        posting1 = await _make_posting(db)
        posting2 = await _make_posting(db)
        posting3 = await _make_posting(db)
        older = await _make_match(
            db, test_user.id, posting1, created_at=datetime.now(UTC) - timedelta(hours=2)
        )
        newer = await _make_match(
            db, test_user.id, posting2, created_at=datetime.now(UTC) - timedelta(hours=1)
        )
        newest = await _make_match(db, test_user.id, posting3, created_at=datetime.now(UTC))

        rows, _ = await repository.list_tracked_matches(
            db, test_user.id, status=None, sort="oldest", limit=20, offset=0
        )
        result_ids = [m.id for m, _ in rows]

        assert result_ids == [older.id, newer.id, newest.id]

    async def test_sort_score_orders_by_overall_score_descending(
        self, db: AsyncSession, test_user: User
    ):
        posting1 = await _make_posting(db)
        posting2 = await _make_posting(db)
        posting3 = await _make_posting(db)
        low = await _make_match(db, test_user.id, posting1, overall_score=10.0)
        high = await _make_match(db, test_user.id, posting2, overall_score=90.0)
        mid = await _make_match(db, test_user.id, posting3, overall_score=50.0)

        rows, _ = await repository.list_tracked_matches(
            db, test_user.id, status=None, sort="score", limit=20, offset=0
        )
        result_ids = [m.id for m, _ in rows]

        assert result_ids == [high.id, mid.id, low.id]

    async def test_sort_score_manual_entry_sorts_last_despite_zero_score_tie(
        self, db: AsyncSession, test_user: User
    ):
        """Regression test: `overall_score` is nullable=False, so a manual entry's
        0.0 sentinel is indistinguishable from a real match that legitimately
        scored 0.0 (e.g. via compute_overall_score's clamp) if the tie-break only
        looks at `overall_score.is_(None)` (always False, dead code). The
        tie-break must instead key off `job_posting_id IS NULL` so the manual
        entry sorts last regardless of the 0.0/0.0 collision on the underlying
        sentinel value, and regardless of insertion order.
        """
        posting = await _make_posting(db)
        real_zero_score_match = await _make_match(db, test_user.id, posting, overall_score=0.0)
        entry = await _make_manual_entry(db, test_user.id)
        manual_match = await _make_manual_match(db, test_user.id, entry)

        rows, _ = await repository.list_tracked_matches(
            db, test_user.id, status=None, sort="score", limit=20, offset=0
        )
        result_ids = [m.id for m, _ in rows]

        assert result_ids == [real_zero_score_match.id, manual_match.id]
        assert result_ids[-1] == manual_match.id

    async def test_sort_score_manual_entry_sorts_last_regardless_of_insertion_order(
        self, db: AsyncSession, test_user: User
    ):
        """Same assertion as above, but with the manual entry inserted BEFORE the
        real zero-score match, to confirm the ordering comes from the SQL
        ORDER BY clause and not from insertion/row order."""
        entry = await _make_manual_entry(db, test_user.id)
        manual_match = await _make_manual_match(db, test_user.id, entry)
        posting = await _make_posting(db)
        real_zero_score_match = await _make_match(db, test_user.id, posting, overall_score=0.0)

        rows, _ = await repository.list_tracked_matches(
            db, test_user.id, status=None, sort="score", limit=20, offset=0
        )
        result_ids = [m.id for m, _ in rows]

        assert result_ids == [real_zero_score_match.id, manual_match.id]

    async def test_sort_recently_updated_puts_never_updated_rows_last_regardless_of_dialect(
        self, db: AsyncSession, test_user: User
    ):
        """NULL-sort tie-break: `status_updated_at IS NULL` must sort LAST for every
        dialect. SQLite's native NULL ordering (NULLs first) would otherwise put
        never-updated rows at the FRONT of a DESC sort, which is why
        `_SORT_COLUMNS["recently_updated"]` leads with the explicit `.is_(None)`
        tie-break column rather than relying on `status_updated_at.desc()` alone.
        """
        posting_never_updated = await _make_posting(db)
        posting_updated_earlier = await _make_posting(db)
        posting_updated_later = await _make_posting(db)

        never_updated = await _make_match(db, test_user.id, posting_never_updated)
        updated_earlier = await _make_match(db, test_user.id, posting_updated_earlier)
        updated_later = await _make_match(db, test_user.id, posting_updated_later)

        # Explicitly set distinct status_updated_at timestamps (not relying on
        # update_status's `now()` call, so ordering between the two updated rows
        # is deterministic rather than racing on wall-clock resolution).
        await db.execute(
            update(JobMatch)
            .where(JobMatch.id == updated_earlier.id)
            .values(
                application_status="applied",
                status_updated_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
        await db.execute(
            update(JobMatch)
            .where(JobMatch.id == updated_later.id)
            .values(application_status="applied", status_updated_at=datetime.now(UTC))
        )
        await db.commit()

        rows, _ = await repository.list_tracked_matches(
            db, test_user.id, status=None, sort="recently_updated", limit=20, offset=0
        )
        result_ids = [m.id for m, _ in rows]

        # never_updated (status_updated_at IS NULL) must be last, despite SQLite's
        # default NULLS-FIRST behavior for a plain `.desc()` ordering.
        assert result_ids == [updated_later.id, updated_earlier.id, never_updated.id]

    async def test_sort_recently_updated_tie_breaks_null_rows_by_created_at_descending(
        self, db: AsyncSession, test_user: User
    ):
        """Among rows that were never manually updated (status_updated_at IS NULL),
        the secondary tie-break is created_at DESC."""
        posting1 = await _make_posting(db)
        posting2 = await _make_posting(db)
        older_never_updated = await _make_match(
            db, test_user.id, posting1, created_at=datetime.now(UTC) - timedelta(hours=2)
        )
        newer_never_updated = await _make_match(
            db, test_user.id, posting2, created_at=datetime.now(UTC) - timedelta(hours=1)
        )

        rows, _ = await repository.list_tracked_matches(
            db, test_user.id, status=None, sort="recently_updated", limit=20, offset=0
        )
        result_ids = [m.id for m, _ in rows]

        assert result_ids == [newer_never_updated.id, older_never_updated.id]


class TestUpdateStatus:
    async def test_updates_status_and_status_updated_at(self, db: AsyncSession, test_user: User):
        posting = await _make_posting(db)
        match = await _make_match(db, test_user.id, posting)
        assert match.application_status == "new"
        assert match.status_updated_at is None

        updated = await repository.update_status(db, match.id, test_user.id, "applied")

        assert updated is not None
        assert updated.application_status == "applied"
        assert updated.status_updated_at is not None

    async def test_returns_none_for_wrong_user(
        self, db: AsyncSession, test_user: User, second_test_user: User
    ):
        posting = await _make_posting(db)
        match = await _make_match(db, test_user.id, posting)

        result = await repository.update_status(db, match.id, second_test_user.id, "applied")

        assert result is None

    async def test_returns_none_for_nonexistent_match(self, db: AsyncSession, test_user: User):
        result = await repository.update_status(db, uuid.uuid4(), test_user.id, "applied")
        assert result is None


class TestCountByStatus:
    async def test_zero_fills_every_status(self, db: AsyncSession, test_user: User):
        posting = await _make_posting(db)
        await _make_match(db, test_user.id, posting)

        counts = await repository.count_by_status(db, test_user.id)

        assert set(counts.keys()) == {
            "new",
            "applied",
            "replied",
            "interview",
            "offer",
            "rejected",
        }
        assert counts["new"] == 1
        assert counts["replied"] == 0
        assert counts["interview"] == 0
        assert counts["offer"] == 0
        assert counts["rejected"] == 0

    async def test_counts_reflect_status_transitions(self, db: AsyncSession, test_user: User):
        posting1 = await _make_posting(db)
        posting2 = await _make_posting(db)
        posting3 = await _make_posting(db)
        match1 = await _make_match(db, test_user.id, posting1)
        match2 = await _make_match(db, test_user.id, posting2)
        await _make_match(db, test_user.id, posting3)

        await repository.update_status(db, match1.id, test_user.id, "applied")
        await repository.update_status(db, match2.id, test_user.id, "applied")

        counts = await repository.count_by_status(db, test_user.id)

        assert counts["applied"] == 2
        assert counts["new"] == 1

    async def test_scoped_per_user(self, db: AsyncSession, test_user: User, second_test_user: User):
        posting1 = await _make_posting(db)
        posting2 = await _make_posting(db)
        await _make_match(db, test_user.id, posting1)
        await _make_match(db, second_test_user.id, posting2)

        counts = await repository.count_by_status(db, test_user.id)

        assert counts["new"] == 1


class TestOwnershipScoping:
    async def test_another_users_match_never_returned(
        self, db: AsyncSession, test_user: User, second_test_user: User
    ):
        own_posting = await _make_posting(db)
        other_posting = await _make_posting(db)
        own_match = await _make_match(db, test_user.id, own_posting)
        await _make_match(db, second_test_user.id, other_posting)

        rows, total = await repository.list_tracked_matches(
            db, test_user.id, status=None, sort="newest", limit=20, offset=0
        )

        result_ids = {m.id for m, _ in rows}
        assert own_match.id in result_ids
        assert total == len(rows)
        for m, _ in rows:
            assert m.user_id == test_user.id

    async def test_get_owned_match_rejects_foreign_match(
        self, db: AsyncSession, test_user: User, second_test_user: User
    ):
        posting = await _make_posting(db)
        match = await _make_match(db, test_user.id, posting)

        owned_by_other = await job_matching_repository.get_owned_match(
            db, match.id, second_test_user.id
        )
        assert owned_by_other is None

        owned_by_actual_owner = await job_matching_repository.get_owned_match(
            db, match.id, test_user.id
        )
        assert owned_by_actual_owner is not None


class TestManualEntrySafety:
    """Regression tests (Module F, §10.6): a manual-entry JobMatch (job_posting_id
    NULL, manual_job_entry_id set) must never raise an AttributeError/crash in the
    tracker's two core repository reads. `get_owned_match` already outer-joined
    JobPosting before this chunk (§6.5's forward-compat note) — this test class
    exercises it directly against a real manual-entry row to confirm that claim,
    rather than trusting the docstring.
    """

    async def test_list_tracked_matches_includes_manual_entry_with_no_crash(
        self, db: AsyncSession, test_user: User
    ):
        entry = await _make_manual_entry(db, test_user.id)
        manual_match = await _make_manual_match(db, test_user.id, entry)
        posting = await _make_posting(db)
        real_match = await _make_match(db, test_user.id, posting)

        rows, total = await repository.list_tracked_matches(
            db, test_user.id, status=None, sort="newest", limit=20, offset=0
        )

        assert total == 2
        rows_by_id = {m.id: (m, p) for m, p in rows}
        manual_row = rows_by_id[manual_match.id]
        assert manual_row[1] is None  # outer-joined JobPosting is None for a manual row
        real_row = rows_by_id[real_match.id]
        assert real_row[1] is not None

    async def test_get_owned_match_returns_none_posting_for_manual_entry_with_no_crash(
        self, db: AsyncSession, test_user: User
    ):
        entry = await _make_manual_entry(db, test_user.id)
        manual_match = await _make_manual_match(db, test_user.id, entry)

        owned = await job_matching_repository.get_owned_match(db, manual_match.id, test_user.id)

        assert owned is not None
        match, posting = owned
        assert match.id == manual_match.id
        assert posting is None  # confirmed safe: outerjoin, no crash unpacking the row

    async def test_service_list_tracked_shows_manual_entry_title_and_null_score(
        self, db: AsyncSession, test_user: User
    ):
        """End-to-end through application_tracker/service.py: a manual entry's
        title/company must come from ManualJobEntry (not blank strings), and
        overall_score must be None (the 0.0 sentinel must never leak to the response).
        """
        from app.modules.application_tracker.service import list_tracked

        entry = await _make_manual_entry(
            db, test_user.id, title="Growth Marketer", company="Startup Co"
        )
        await _make_manual_match(db, test_user.id, entry)

        result = await list_tracked(
            db, test_user.id, status=None, sort="newest", limit=20, offset=0
        )

        assert len(result.matches) == 1
        manual_response = result.matches[0]
        assert manual_response.title == "Growth Marketer"
        assert manual_response.company == "Startup Co"
        assert manual_response.overall_score is None
        assert manual_response.job_posting_id == ""
