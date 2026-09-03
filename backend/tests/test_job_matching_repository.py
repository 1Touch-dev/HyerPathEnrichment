"""Repository-layer tests for job matching, using the shared test DB fixture.

Adapted from phase2_module1.md §8.2: the spec assumed `db_session`, `test_user`,
and `second_test_user` fixtures existed in conftest.py. They don't — the real
async session fixture is `db`, and there is no shared user fixture, so
`test_user`/`second_test_user` are defined locally here (same pattern as
`active_user` in test_account_deletion.py).
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.password import hash_password
from app.modules.job_matching import repository
from app.modules.job_matching.models import PGVECTOR_AVAILABLE, JobPosting, JobPostingEmbedding
from app.modules.job_matching.scorer import compute_dedup_key
from app.modules.manual_jobs.models import ManualJobEntry
from app.observability.job_matching_metrics import job_matching_similarity_fallback_fired_total


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    """Primary candidate user for job-matching repository tests."""
    user = User(
        email=f"jobmatch-primary-{uuid.uuid4().hex[:8]}@example.com",
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
    """Secondary candidate user, distinct row from `test_user`."""
    user = User(
        email=f"jobmatch-secondary-{uuid.uuid4().hex[:8]}@example.com",
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
    """Create and commit a JobPosting row with sensible defaults, unique dedup_key."""
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


async def _make_manual_entry(db: AsyncSession, user_id: uuid.UUID, **overrides) -> ManualJobEntry:
    """Create and commit a ManualJobEntry row (Module F, §10.5) with sensible defaults."""
    fields = {
        "user_id": user_id,
        "title": "Self-Sourced Engineer",
        "company": "Referral Co",
        "location": "Remote",
        "source_label": "Referral",
        "source_url": "https://example.com/careers/manual",
        "notes": None,
    }
    fields.update(overrides)
    entry = ManualJobEntry(**fields)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def _make_manual_match(
    db: AsyncSession, user_id: uuid.UUID, entry: ManualJobEntry, **overrides
) -> Any:
    """Create and commit a JobMatch row wired to a manual entry (job_posting_id=None,
    manual_job_entry_id set) — the exact shape manual_jobs/repository.py's
    create_manual_entry() produces (Module F, §10.5), used here directly rather than
    going through the manual_jobs module to keep these repository tests scoped to
    job_matching only.
    """
    from app.modules.job_matching.models import JobMatch

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


class TestPreferencesRepository:
    async def test_upsert_creates_new_preferences(self, db: AsyncSession, test_user: User):
        prefs = await repository.upsert_preferences(
            db, test_user.id, {"desired_roles": ["Backend Engineer"], "salary_min": 100_000}
        )
        assert prefs.desired_roles == ["Backend Engineer"]
        assert prefs.salary_min == 100_000
        assert prefs.is_scan_enabled is True

    async def test_upsert_updates_existing_preferences(self, db: AsyncSession, test_user: User):
        await repository.upsert_preferences(db, test_user.id, {"salary_min": 100_000})
        updated = await repository.upsert_preferences(db, test_user.id, {"salary_min": 150_000})
        assert updated.salary_min == 150_000

        fetched = await repository.get_preferences(db, test_user.id)
        assert fetched.salary_min == 150_000

    async def test_get_preferences_returns_none_when_missing(self, db: AsyncSession):
        result = await repository.get_preferences(db, uuid.uuid4())
        assert result is None

    async def test_list_scan_enabled_excludes_disabled(
        self, db: AsyncSession, test_user: User, second_test_user: User
    ):
        await repository.upsert_preferences(db, test_user.id, {"is_scan_enabled": True})
        await repository.upsert_preferences(db, second_test_user.id, {"is_scan_enabled": False})

        enabled = await repository.list_scan_enabled_preferences(db, limit=100, offset=0)
        enabled_ids = {p.user_id for p in enabled}
        assert test_user.id in enabled_ids
        assert second_test_user.id not in enabled_ids


class TestJobPostingRepository:
    async def test_upsert_creates_new_posting(self, db: AsyncSession):
        dedup_key = compute_dedup_key("Backend Engineer", "Remote", "linkedin")
        posting = await repository.upsert_job_posting(
            db,
            dedup_key,
            {
                "title": "Backend Engineer",
                "company": "Acme",
                "location": "Remote",
                "remote": True,
                "source": "linkedin",
            },
            "linkedin",
        )
        assert posting.id is not None
        assert posting.sources_seen == ["linkedin"]

    async def test_upsert_same_dedup_key_merges_sources(self, db: AsyncSession):
        dedup_key = compute_dedup_key("Backend Engineer", "Remote", "linkedin")
        first = await repository.upsert_job_posting(
            db,
            dedup_key,
            {
                "title": "Backend Engineer",
                "company": "Acme",
                "location": "Remote",
                "remote": True,
                "source": "linkedin",
            },
            "linkedin",
        )
        second = await repository.upsert_job_posting(
            db,
            dedup_key,
            {
                "title": "Backend Engineer",
                "company": "Acme",
                "location": "Remote",
                "remote": True,
                "source": "indeed",
            },
            "indeed",
        )
        assert first.id == second.id  # same row, not a duplicate
        assert set(second.sources_seen) == {"linkedin", "indeed"}

    async def test_find_posting_by_dedup_key_returns_none_when_missing(self, db: AsyncSession):
        result = await repository.find_posting_by_dedup_key(db, "does-not-exist")
        assert result is None


class TestPostingEmbeddingRepository:
    async def test_store_creates_new_embedding(self, db: AsyncSession):
        posting = await _make_posting(db)
        embedding = [0.1, 0.2, 0.3]

        await repository.store_posting_embedding(db, posting.id, embedding, token_count=42)

        result = await db.execute(
            select(JobPostingEmbedding).where(JobPostingEmbedding.job_posting_id == posting.id)
        )
        row = result.scalar_one()
        assert list(row.embedding) == embedding
        assert row.token_count == 42

    async def test_store_updates_existing_embedding(self, db: AsyncSession):
        posting = await _make_posting(db)

        await repository.store_posting_embedding(db, posting.id, [0.1, 0.2, 0.3], token_count=10)
        await repository.store_posting_embedding(db, posting.id, [0.4, 0.5, 0.6], token_count=20)

        result = await db.execute(
            select(JobPostingEmbedding).where(JobPostingEmbedding.job_posting_id == posting.id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1  # updated in place, not duplicated
        assert list(rows[0].embedding) == [0.4, 0.5, 0.6]
        assert rows[0].token_count == 20

    async def test_has_posting_embedding_returns_false_when_missing(self, db: AsyncSession):
        posting = await _make_posting(db)
        assert await repository.has_posting_embedding(db, posting.id) is False

    async def test_has_posting_embedding_returns_true_after_store(self, db: AsyncSession):
        posting = await _make_posting(db)
        await repository.store_posting_embedding(db, posting.id, [0.1, 0.2, 0.3], token_count=42)
        assert await repository.has_posting_embedding(db, posting.id) is True

    @pytest.mark.skipif(
        PGVECTOR_AVAILABLE,
        reason=(
            "Exercises the SQLite-JSON-fallback `embedding` property on "
            "JobPostingEmbedding, which is only compiled in when the `pgvector` "
            "package is NOT importable (see models.py's PGVECTOR_AVAILABLE branch). "
            "This environment has pgvector installed, so the ORM uses the real "
            "Vector(1536) column instead and `_embedding_json` never exists — "
            "run with pgvector uninstalled (or in an environment without it) to "
            "actually exercise this fallback path."
        ),
    )
    async def test_embedding_getter_parses_json_string_on_sqlite(self, db: AsyncSession):
        """Guards against a latent AttributeError in the SQLite-fallback `embedding`
        property getter (§ audit item 3): force a genuine DB round-trip so the row
        is reloaded with `_embedding_json` as a raw JSON string (not the list
        object still cached from the setter in this session), then confirm the
        getter parses it back into a list without raising.
        """
        posting = await _make_posting(db)
        posting_id = posting.id
        embedding = [0.25, -0.5, 0.75]

        await repository.store_posting_embedding(db, posting_id, embedding, token_count=7)

        db.expire_all()
        result = await db.execute(
            select(JobPostingEmbedding).where(JobPostingEmbedding.job_posting_id == posting_id)
        )
        row = result.scalar_one()
        assert isinstance(row._embedding_json, str)  # confirms this exercises the parse path
        assert row.embedding == pytest.approx(embedding)


class TestJobMatchRepository:
    async def test_upsert_creates_new_match(self, db: AsyncSession, test_user: User):
        posting = await _make_posting(db)
        match = await repository.upsert_match(
            db,
            test_user.id,
            posting.id,
            similarity_score=0.8,
            rule_score=0.6,
            overall_score=74.0,
            score_breakdown={"salary_fit": 1.0, "location_fit": 0.5},
        )
        assert match.id is not None
        assert match.similarity_score == 0.8
        assert match.overall_score == 74.0

    async def test_upsert_updates_existing_match_on_conflict(
        self, db: AsyncSession, test_user: User
    ):
        posting = await _make_posting(db)
        first = await repository.upsert_match(
            db,
            test_user.id,
            posting.id,
            similarity_score=0.5,
            rule_score=0.5,
            overall_score=50.0,
            score_breakdown={},
        )
        second = await repository.upsert_match(
            db,
            test_user.id,
            posting.id,
            similarity_score=0.9,
            rule_score=0.9,
            overall_score=90.0,
            score_breakdown={"salary_fit": 1.0},
        )
        assert first.id == second.id  # unique (user_id, job_posting_id) — refreshed, not duplicated
        assert second.overall_score == 90.0

        result = await db.execute(
            select(repository.JobMatch).where(repository.JobMatch.user_id == test_user.id)
        )
        assert len(result.scalars().all()) == 1

    async def test_list_matches_for_user_pagination(self, db: AsyncSession, test_user: User):
        postings = [await _make_posting(db) for _ in range(3)]
        for i, posting in enumerate(postings):
            await repository.upsert_match(
                db,
                test_user.id,
                posting.id,
                similarity_score=0.5,
                rule_score=0.5,
                overall_score=float(10 * (i + 1)),
                score_breakdown={},
            )

        page1, total1 = await repository.list_matches_for_user(db, test_user.id, limit=2, offset=0)
        assert total1 == 3
        assert len(page1) == 2
        # ordered by overall_score desc
        assert page1[0][0].overall_score == 30.0
        assert page1[1][0].overall_score == 20.0

        page2, total2 = await repository.list_matches_for_user(db, test_user.id, limit=2, offset=2)
        assert total2 == 3
        assert len(page2) == 1
        assert page2[0][0].overall_score == 10.0

    async def test_list_matches_for_user_includes_manual_entry_with_no_crash(
        self, db: AsyncSession, test_user: User
    ):
        """Regression test (Module F, §10.6): a manual-entry JobMatch (job_posting_id
        NULL, manual_job_entry_id set) must not be silently dropped by an inner join,
        and must not raise when the row is unpacked — it comes back with posting=None
        and the manual entry populated, sourced separately.
        """
        entry = await _make_manual_entry(
            db, test_user.id, title="Self-Sourced Role", company="Referral Co"
        )
        manual_match = await _make_manual_match(db, test_user.id, entry)

        posting = await _make_posting(db)
        real_match = await repository.upsert_match(
            db,
            test_user.id,
            posting.id,
            similarity_score=0.5,
            rule_score=0.5,
            overall_score=50.0,
            score_breakdown={},
        )

        rows, total = await repository.list_matches_for_user(db, test_user.id, limit=10, offset=0)
        assert total == 2

        rows_by_id = {m.id: (m, p, e) for m, p, e in rows}
        manual_row = rows_by_id[manual_match.id]
        assert manual_row[1] is None  # no JobPosting row
        assert manual_row[2] is not None  # ManualJobEntry row is populated
        assert manual_row[2].title == "Self-Sourced Role"
        assert manual_row[2].company == "Referral Co"

        real_row = rows_by_id[real_match.id]
        assert real_row[1] is not None
        assert real_row[2] is None

        title, company, _, _ = repository.resolve_match_display_fields(manual_row[1], manual_row[2])
        assert title == "Self-Sourced Role"
        assert company == "Referral Co"

    async def test_get_top_unexplained_matches_filters_explained_and_respects_top_n(
        self, db: AsyncSession, test_user: User
    ):
        postings = [await _make_posting(db) for _ in range(3)]
        matches = []
        for i, posting in enumerate(postings):
            m = await repository.upsert_match(
                db,
                test_user.id,
                posting.id,
                similarity_score=0.5,
                rule_score=0.5,
                overall_score=float(10 * (i + 1)),
                score_breakdown={},
            )
            matches.append(m)

        # Explain the highest-scoring match; it should be excluded from unexplained results.
        await repository.save_explanation(
            db, matches[2].id, "This role fits your backend experience."
        )

        top = await repository.get_top_unexplained_matches(db, test_user.id, top_n=5)
        top_ids = {m.id for m, _ in top}
        assert matches[2].id not in top_ids
        assert matches[1].id in top_ids
        assert matches[0].id in top_ids

        limited = await repository.get_top_unexplained_matches(db, test_user.id, top_n=1)
        assert len(limited) == 1
        assert limited[0][0].id == matches[1].id  # highest-scoring remaining unexplained match

    async def test_get_top_unexplained_matches_excludes_manual_entries_with_no_crash(
        self, db: AsyncSession, test_user: User
    ):
        """Regression test (Module F, §10.6): manual entries have no JD-embedding to
        explain a similarity match against, so they must never surface here — and the
        (now inner-joined-with-a-NULL-guard) query must not raise on their presence.
        """
        entry = await _make_manual_entry(db, test_user.id)
        await _make_manual_match(db, test_user.id, entry, overall_score=999.0)

        posting = await _make_posting(db)
        real_match = await repository.upsert_match(
            db,
            test_user.id,
            posting.id,
            similarity_score=0.5,
            rule_score=0.5,
            overall_score=10.0,
            score_breakdown={},
        )

        top = await repository.get_top_unexplained_matches(db, test_user.id, top_n=5)
        top_ids = {m.id for m, _ in top}
        assert real_match.id in top_ids
        # The manual entry's sentinel overall_score=999.0 would otherwise rank first —
        # confirming its absence also confirms it isn't merely sorted last.
        assert len(top) == 1

    async def test_save_explanation_sets_fields(self, db: AsyncSession, test_user: User):
        posting = await _make_posting(db)
        match = await repository.upsert_match(
            db,
            test_user.id,
            posting.id,
            similarity_score=0.5,
            rule_score=0.5,
            overall_score=50.0,
            score_breakdown={},
        )
        assert match.explanation is None

        await repository.save_explanation(db, match.id, "Great fit for your skills.")

        result = await db.execute(
            select(repository.JobMatch).where(repository.JobMatch.id == match.id)
        )
        refreshed = result.scalar_one()
        assert refreshed.explanation == "Great fit for your skills."
        assert refreshed.explanation_generated_at is not None

    async def test_mark_notified_sets_timestamp_for_multiple_matches(
        self, db: AsyncSession, test_user: User
    ):
        postings = [await _make_posting(db) for _ in range(2)]
        matches = [
            await repository.upsert_match(
                db,
                test_user.id,
                p.id,
                similarity_score=0.5,
                rule_score=0.5,
                overall_score=50.0,
                score_breakdown={},
            )
            for p in postings
        ]

        await repository.mark_notified(db, [m.id for m in matches])

        result = await db.execute(
            select(repository.JobMatch).where(repository.JobMatch.id.in_([m.id for m in matches]))
        )
        for row in result.scalars().all():
            assert row.notified_at is not None

    async def test_mark_notified_noop_on_empty_list(self, db: AsyncSession):
        # Should not raise even though no ids given.
        await repository.mark_notified(db, [])

    async def test_mark_viewed_returns_false_for_already_viewed_or_wrong_user(
        self, db: AsyncSession, test_user: User, second_test_user: User
    ):
        posting = await _make_posting(db)
        match = await repository.upsert_match(
            db,
            test_user.id,
            posting.id,
            similarity_score=0.5,
            rule_score=0.5,
            overall_score=50.0,
            score_breakdown={},
        )

        wrong_user_result = await repository.mark_viewed(db, match.id, second_test_user.id)
        assert wrong_user_result is False

        first_view = await repository.mark_viewed(db, match.id, test_user.id)
        assert first_view is True

        second_view = await repository.mark_viewed(db, match.id, test_user.id)
        assert second_view is False  # already viewed

    async def test_set_feedback_updates_value_and_rejects_wrong_user(
        self, db: AsyncSession, test_user: User, second_test_user: User
    ):
        posting = await _make_posting(db)
        match = await repository.upsert_match(
            db,
            test_user.id,
            posting.id,
            similarity_score=0.5,
            rule_score=0.5,
            overall_score=50.0,
            score_breakdown={},
        )

        wrong_user_result = await repository.set_feedback(db, match.id, second_test_user.id, "up")
        assert wrong_user_result is False

        ok = await repository.set_feedback(db, match.id, test_user.id, "up")
        assert ok is True

        result = await db.execute(
            select(repository.JobMatch).where(repository.JobMatch.id == match.id)
        )
        refreshed = result.scalar_one()
        assert refreshed.feedback == "up"


class TestClaimMatchForExplanation:
    async def test_claim_succeeds_once_then_loses_the_race_on_second_call(
        self, db: AsyncSession, test_user: User
    ):
        posting = await _make_posting(db)
        match = await repository.upsert_match(
            db,
            test_user.id,
            posting.id,
            similarity_score=0.5,
            rule_score=0.5,
            overall_score=50.0,
            score_breakdown={},
        )

        first_claim = await repository.claim_match_for_explanation(db, match.id)
        assert first_claim is True

        second_claim = await repository.claim_match_for_explanation(db, match.id)
        assert second_claim is False

        result = await db.execute(
            select(repository.JobMatch).where(repository.JobMatch.id == match.id)
        )
        refreshed = result.scalar_one()
        assert refreshed.explanation_status == "processing"

    async def test_claim_returns_false_for_nonexistent_match(self, db: AsyncSession):
        assert await repository.claim_match_for_explanation(db, uuid.uuid4()) is False


class TestRecordExplanationFailure:
    async def test_requeues_as_not_explained_while_under_max_retries(
        self, db: AsyncSession, test_user: User
    ):
        posting = await _make_posting(db)
        match = await repository.upsert_match(
            db,
            test_user.id,
            posting.id,
            similarity_score=0.5,
            rule_score=0.5,
            overall_score=50.0,
            score_breakdown={},
        )
        await repository.claim_match_for_explanation(db, match.id)

        await repository.record_explanation_failure(
            db, match.id, error_message="LLM timeout", max_retries=3
        )

        result = await db.execute(
            select(repository.JobMatch).where(repository.JobMatch.id == match.id)
        )
        refreshed = result.scalar_one()
        assert refreshed.explanation_status == "not_explained"
        assert refreshed.retry_count == 1
        assert refreshed.is_error is True
        assert refreshed.last_error == "LLM timeout"

    async def test_transitions_to_failed_once_max_retries_reached(
        self, db: AsyncSession, test_user: User
    ):
        posting = await _make_posting(db)
        match = await repository.upsert_match(
            db,
            test_user.id,
            posting.id,
            similarity_score=0.5,
            rule_score=0.5,
            overall_score=50.0,
            score_breakdown={},
        )

        for _ in range(3):
            await repository.claim_match_for_explanation(db, match.id)
            await repository.record_explanation_failure(
                db, match.id, error_message="LLM timeout", max_retries=3
            )

        result = await db.execute(
            select(repository.JobMatch).where(repository.JobMatch.id == match.id)
        )
        refreshed = result.scalar_one()
        assert refreshed.explanation_status == "failed"
        assert refreshed.retry_count == 3
        assert refreshed.is_error is True
        assert refreshed.last_error == "LLM timeout"


class TestCountUnreadMatches:
    async def test_returns_zero_for_user_with_no_matches(self, db: AsyncSession, test_user: User):
        count = await repository.count_unread_matches(db, test_user.id)
        assert count == 0

    async def test_counts_only_unviewed_matches(self, db: AsyncSession, test_user: User):
        postings = [await _make_posting(db) for _ in range(3)]
        matches = [
            await repository.upsert_match(
                db,
                test_user.id,
                p.id,
                similarity_score=0.5,
                rule_score=0.5,
                overall_score=50.0,
                score_breakdown={},
            )
            for p in postings
        ]

        await repository.mark_viewed(db, matches[0].id, test_user.id)

        count = await repository.count_unread_matches(db, test_user.id)
        assert count == 2  # matches[1] and matches[2] still have viewed_at=None

    async def test_scoped_per_user(self, db: AsyncSession, test_user: User, second_test_user: User):
        posting = await _make_posting(db)
        other_posting = await _make_posting(db)

        await repository.upsert_match(
            db,
            test_user.id,
            posting.id,
            similarity_score=0.5,
            rule_score=0.5,
            overall_score=50.0,
            score_breakdown={},
        )
        await repository.upsert_match(
            db,
            second_test_user.id,
            other_posting.id,
            similarity_score=0.5,
            rule_score=0.5,
            overall_score=50.0,
            score_breakdown={},
        )

        assert await repository.count_unread_matches(db, test_user.id) == 1
        assert await repository.count_unread_matches(db, second_test_user.id) == 1

        # Second user's match doesn't affect the first user's count even after viewing it.
        second_user_matches, _ = await repository.list_matches_for_user(
            db, second_test_user.id, limit=10, offset=0
        )
        await repository.mark_viewed(db, second_user_matches[0][0].id, second_test_user.id)

        assert await repository.count_unread_matches(db, test_user.id) == 1
        assert await repository.count_unread_matches(db, second_test_user.id) == 0


class TestFindSimilarPostings:
    async def test_returns_similarity_score_for_matching_embedding(self, db: AsyncSession):
        posting = await _make_posting(db)
        await repository.store_posting_embedding(db, posting.id, [1.0, 0.0, 0.0], token_count=5)

        results = await repository.find_similar_postings(
            db,
            query_embedding=[1.0, 0.0, 0.0],
            limit=10,
            similarity_threshold=0.5,
            min_results=1,
        )

        assert len(results) == 1
        result_id, similarity, passed_threshold = results[0]
        assert result_id == posting.id
        assert similarity == pytest.approx(1.0, abs=1e-6)
        assert passed_threshold is True

    async def test_respects_similarity_threshold(self, db: AsyncSession):
        posting = await _make_posting(db)
        # Orthogonal vector -> cosine similarity of 0.0, below any positive threshold.
        await repository.store_posting_embedding(db, posting.id, [0.0, 1.0, 0.0], token_count=5)

        # Scope to this posting via posting_ids since the test DB persists committed
        # rows across tests (no per-test transaction rollback), so unscoped queries
        # would also pick up matching postings from other tests. min_results=0 keeps
        # the fallback pass from firing (it would otherwise relax the threshold and
        # pull this posting back in, defeating the point of this test).
        results = await repository.find_similar_postings(
            db,
            query_embedding=[1.0, 0.0, 0.0],
            limit=10,
            similarity_threshold=0.5,
            posting_ids=[posting.id],
            min_results=0,
        )
        assert results == []

    async def test_respects_posting_ids_filter(self, db: AsyncSession):
        included = await _make_posting(db)
        excluded = await _make_posting(db)
        await repository.store_posting_embedding(db, included.id, [1.0, 0.0, 0.0], token_count=5)
        await repository.store_posting_embedding(db, excluded.id, [1.0, 0.0, 0.0], token_count=5)

        results = await repository.find_similar_postings(
            db,
            query_embedding=[1.0, 0.0, 0.0],
            limit=10,
            similarity_threshold=0.5,
            posting_ids=[included.id],
            min_results=1,
        )

        result_ids = {r[0] for r in results}
        assert result_ids == {included.id}

    async def test_excludes_inactive_postings(self, db: AsyncSession):
        posting = await _make_posting(db, is_active=False)
        await repository.store_posting_embedding(db, posting.id, [1.0, 0.0, 0.0], token_count=5)

        # Scope to this posting via posting_ids for the same reason as above: it's
        # excluded by is_active regardless, but this avoids depending on other tests'
        # leftover active postings sharing the same embedding to prove the point.
        # min_results=0 keeps the fallback pass from firing.
        results = await repository.find_similar_postings(
            db,
            query_embedding=[1.0, 0.0, 0.0],
            limit=10,
            similarity_threshold=0.5,
            posting_ids=[posting.id],
            min_results=0,
        )
        assert results == []

    async def test_respects_limit(self, db: AsyncSession):
        postings = [await _make_posting(db) for _ in range(3)]
        for posting in postings:
            await repository.store_posting_embedding(db, posting.id, [1.0, 0.0, 0.0], token_count=5)

        results = await repository.find_similar_postings(
            db,
            query_embedding=[1.0, 0.0, 0.0],
            limit=2,
            similarity_threshold=0.5,
            min_results=0,
        )
        assert len(results) == 2

    async def test_postgres_path_binds_embedding_as_parameter_not_literal(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ):
        """Guards against SQL string-interpolation of the embedding vector (audit
        item 4): forces the Postgres branch by pointing settings at a Postgres
        URL, then intercepts the exact statement/params passed to `db.execute()`
        (no real Postgres needed) to confirm the embedding values are bound as
        query parameters rather than baked into the SQL text.
        """
        from app.core.config import get_settings

        monkeypatch.setattr(get_settings(), "database_url", "postgresql+asyncpg://fake/db")

        captured: dict[str, Any] = {}
        original_execute = db.execute

        async def spy_execute(statement, params=None, *args, **kwargs):
            if isinstance(params, dict) and "query_embedding" in params:
                captured["sql_text"] = str(statement)
                captured["params"] = params
                raise RuntimeError("no real Postgres in this test — forces the Python fallback")
            return await original_execute(statement, params, *args, **kwargs)

        monkeypatch.setattr(db, "execute", spy_execute)

        embedding = [0.123456, -0.654321, 0.999999]
        # The simulated failure makes it fall through to the Python/SQLite fallback path,
        # which still runs against this test's real (SQLite) session — that fallback
        # behavior isn't what's under test here, only the captured Postgres-branch call.
        await repository.find_similar_postings(
            db, query_embedding=embedding, limit=5, min_results=0
        )

        assert "sql_text" in captured, "expected the Postgres branch to be exercised"
        assert "0.123456" not in captured["sql_text"]
        assert "-0.654321" not in captured["sql_text"]
        assert "0.999999" not in captured["sql_text"]
        assert captured["params"]["query_embedding"] == "[0.123456,-0.654321,0.999999]"


class TestFindSimilarPostingsFallback:
    """Module A: progressive-relaxation fallback when the strict pass returns fewer
    than `min_results` matches (§5.2/§5.3 of the Module 4 plan).
    """

    async def _make_postings_with_embeddings(
        self, db: AsyncSession, similarities: list[float]
    ) -> list[JobPosting]:
        """Create one posting per similarity value in `similarities`, with an
        embedding engineered (via a 2D unit-circle construction) so its cosine
        similarity to the query embedding [1.0, 0.0] is exactly the requested value.
        """
        import math

        postings = []
        for sim in similarities:
            posting = await _make_posting(db)
            angle = math.acos(max(-1.0, min(1.0, sim)))
            embedding = [math.cos(angle), math.sin(angle)]
            await repository.store_posting_embedding(db, posting.id, embedding, token_count=5)
            postings.append(posting)
        return postings

    async def test_fallback_never_fires_when_strict_pass_has_enough_results(self, db: AsyncSession):
        postings = await self._make_postings_with_embeddings(
            db, [0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.52, 0.51]
        )
        posting_ids = [p.id for p in postings]

        with patch.object(job_matching_similarity_fallback_fired_total, "inc") as mock_inc:
            results = await repository.find_similar_postings(
                db,
                query_embedding=[1.0, 0.0],
                limit=20,
                similarity_threshold=0.5,
                posting_ids=posting_ids,
                min_results=10,
            )

        assert len(results) == 10
        assert all(passed_threshold is True for _pid, _sim, passed_threshold in results)
        mock_inc.assert_not_called()  # fallback did not fire

    async def test_fallback_fires_and_merges_strict_and_relaxed_results(self, db: AsyncSession):
        # 4 postings clear the 0.5 threshold ("strict"); 6 more sit below it but
        # would be picked up by a relaxed (threshold-less) pass ordered by similarity.
        strict_postings = await self._make_postings_with_embeddings(db, [0.9, 0.8, 0.7, 0.6])
        relaxed_postings = await self._make_postings_with_embeddings(
            db, [0.45, 0.4, 0.35, 0.3, 0.25, 0.2]
        )
        posting_ids = [p.id for p in strict_postings + relaxed_postings]

        with patch.object(job_matching_similarity_fallback_fired_total, "inc") as mock_inc:
            results = await repository.find_similar_postings(
                db,
                query_embedding=[1.0, 0.0],
                limit=20,
                similarity_threshold=0.5,
                posting_ids=posting_ids,
                min_results=10,
            )

        mock_inc.assert_called_once()  # counter incremented exactly once

        assert len(results) == 10  # topped up to exactly min_results

        strict_ids = {p.id for p in strict_postings}
        result_by_id = {pid: (sim, passed) for pid, sim, passed in results}

        # All 4 strict results are present, untouched, and still flagged passed_threshold=True.
        for posting in strict_postings:
            assert posting.id in result_by_id
            assert result_by_id[posting.id][1] is True

        # Exactly 6 relaxed results fill the remaining slots up to min_results=10,
        # all flagged passed_threshold=False, and none of them duplicate a strict id.
        relaxed_ids_in_results = set(result_by_id) - strict_ids
        assert len(relaxed_ids_in_results) == 6
        for pid in relaxed_ids_in_results:
            assert result_by_id[pid][1] is False

        # The highest-similarity relaxed postings (0.45 down to 0.2, all 6 of them)
        # are exactly the ones that filled the gap, since relaxed_postings has only 6.
        relaxed_id_set = {p.id for p in relaxed_postings}
        assert relaxed_ids_in_results == relaxed_id_set

    async def test_fallback_never_truncates_strict_results_to_make_room(self, db: AsyncSession):
        """A candidate with 15 genuinely good (above-threshold) matches sees all 15,
        not capped at min_results=10 (§5.2 point 3)."""
        strict_postings = await self._make_postings_with_embeddings(
            db,
            [
                0.9,
                0.85,
                0.8,
                0.75,
                0.7,
                0.65,
                0.6,
                0.58,
                0.56,
                0.54,
                0.52,
                0.51,
                0.505,
                0.502,
                0.501,
            ],
        )
        posting_ids = [p.id for p in strict_postings]

        results = await repository.find_similar_postings(
            db,
            query_embedding=[1.0, 0.0],
            limit=20,
            similarity_threshold=0.5,
            posting_ids=posting_ids,
            min_results=10,
        )

        assert len(results) == 15
        assert all(passed_threshold is True for _pid, _sim, passed_threshold in results)
