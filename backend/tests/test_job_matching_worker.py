"""Tests for app.workers.tasks.job_matching (RQ worker entrypoints).

All worker entrypoints tested here (`scan_jobs_for_candidate`, `generate_explanations_for_candidate`,
`send_match_digest`, `check_worker_health`) are *sync* functions that internally call
`asyncio.run(...)`. Calling `asyncio.run()` from inside an already-running event loop raises
`RuntimeError: asyncio.run() cannot be called from a running event loop`, so these tests are
deliberately plain sync `def test_...` functions (no `@pytest.mark.asyncio`, no `db` fixture) —
each worker call gets to create and fully tear down its own event loop, exactly like it does
in production under RQ.

Because setup/assertions run in plain sync test functions, we use `SyncSessionLocal` (the sync
SQLAlchemy session factory RQ workers also have available) to seed and inspect rows, rather than
the async `db` fixture used elsewhere in this test suite.

External calls mocked (per RULE.md "No live external calls in CI"):
  - JobSpy scraping: `app.enrichers.jobspy.JobSpyEnricher._scrape`
  - OpenAI embeddings: `app.clients.embeddings.get_embeddings_client`
  - OpenAI explanation generation: `app.modules.job_matching.explainer.generate_match_explanation`
  - Email enqueue: `app.workers.queue.enqueue_email`

Everything else (repository.*, scorer.* real DB writes/reads) runs for real against the shared
test SQLite database.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.auth.models import User
from app.database.session import SyncSessionLocal
from app.database.session import engine as _async_engine
from app.modules.documents.models import CandidateDocument, DocumentEmbedding
from app.modules.job_matching.models import (
    CandidateJobPreferences,
    JobMatch,
    JobPosting,
    JobPostingEmbedding,
)
from app.modules.job_matching.scorer import compute_dedup_key
from app.workers.tasks.job_matching import (
    _build_search_term,
    check_worker_health,
    fan_out_daily_scans,
    generate_explanations_for_candidate,
    scan_jobs_for_candidate,
    send_match_digest,
)

FAKE_EMBEDDING = [0.1] * 1536
FAKE_TOKEN_COUNT = 42

FAKE_JOBSPY_ROWS = [
    {
        "title": "Backend Engineer",
        "company": "Acme Corp",
        "location": "Remote",
        "is_remote": True,
        "site": "linkedin",
        "description": "Build and maintain Python backend services at scale.",
        "job_url": "https://example.com/jobs/1",
        "min_amount": 120000,
        "max_amount": 150000,
        "currency": "USD",
    },
    {
        "title": "Senior Software Engineer",
        "company": "Widgets Inc",
        "location": "New York, NY",
        "is_remote": False,
        "site": "indeed",
        "description": "Design and ship distributed systems in Python and Go.",
        "job_url": "https://example.com/jobs/2",
        "min_amount": 130000,
        "max_amount": 160000,
        "currency": "USD",
    },
]


@pytest.fixture(autouse=True)
def _isolate_async_engine_per_test():
    """Dispose the shared async engine's connection pool before/after each test.

    Every sync worker entrypoint wraps `asyncio.run(...)`, which spins up a brand-new event
    loop per call. `_scan_jobs_for_candidate_async` explicitly disposes `engine` in its
    `finally` block, but `_generate_explanations_for_candidate_async` and
    `_send_match_digest_async` do not. A pooled aiosqlite connection created under one
    `asyncio.run()` event loop must never be reused by a *different* `asyncio.run()` event
    loop (asyncio/aiosqlite connections are loop-bound) — that raises confusing cross-loop
    errors. Disposing the pool before and after each test guarantees every worker call in
    every test opens fresh connections tied only to its own fresh loop.
    """
    asyncio.run(_async_engine.dispose())
    yield
    asyncio.run(_async_engine.dispose())


def _create_user(**overrides) -> User:
    with SyncSessionLocal() as session:
        fields = {
            "email": f"jobmatch-worker-{uuid.uuid4().hex[:10]}@example.com",
            "first_name": "Worker",
            "last_name": "Candidate",
            "is_verified": True,
        }
        fields.update(overrides)
        user = User(**fields)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def _create_preferences(user_id, **overrides) -> CandidateJobPreferences:
    with SyncSessionLocal() as session:
        fields = {
            "user_id": user_id,
            "desired_roles": ["Backend Engineer"],
            "desired_locations": ["Remote"],
            "notification_channels": ["email"],
            "is_scan_enabled": True,
        }
        fields.update(overrides)
        prefs = CandidateJobPreferences(**fields)
        session.add(prefs)
        session.commit()
        session.refresh(prefs)
        return prefs


def _create_completed_cv(user_id, *, extracted_data: dict | None = None) -> CandidateDocument:
    with SyncSessionLocal() as session:
        doc = CandidateDocument(
            user_id=user_id,
            document_type="cv",
            original_filename="resume.pdf",
            storage_path=f"/tmp/{uuid.uuid4().hex}.pdf",
            file_hash=uuid.uuid4().hex,
            file_size_bytes=2048,
            raw_text="Experienced backend engineer skilled in Python and SQL.",
            extracted_data=extracted_data if extracted_data is not None else {},
            processing_status="completed",
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)
        return doc


def _create_cv_embedding(document_id, embedding: list[float] | None = None) -> DocumentEmbedding:
    with SyncSessionLocal() as session:
        emb = DocumentEmbedding(
            document_id=document_id,
            chunk_index=0,
            chunk_text="Experienced backend engineer skilled in Python and SQL.",
            token_count=FAKE_TOKEN_COUNT,
        )
        emb.embedding = list(embedding if embedding is not None else FAKE_EMBEDDING)
        session.add(emb)
        session.commit()
        session.refresh(emb)
        return emb


def _create_posting(**overrides) -> JobPosting:
    with SyncSessionLocal() as session:
        fields = {
            "dedup_key": uuid.uuid4().hex,
            "title": "Backend Engineer",
            "company": "Acme Corp",
            "location": "Remote",
            "remote": True,
            "source": "linkedin",
            "sources_seen": ["linkedin"],
            "is_active": True,
        }
        fields.update(overrides)
        posting = JobPosting(**fields)
        session.add(posting)
        session.commit()
        session.refresh(posting)
        return posting


def _create_posting_embedding(job_posting_id, embedding: list[float] | None = None) -> None:
    with SyncSessionLocal() as session:
        emb = JobPostingEmbedding(job_posting_id=job_posting_id, token_count=FAKE_TOKEN_COUNT)
        emb.embedding = list(embedding if embedding is not None else FAKE_EMBEDDING)
        session.add(emb)
        session.commit()


def _create_match(user_id, job_posting_id, **overrides) -> JobMatch:
    with SyncSessionLocal() as session:
        fields = {
            "user_id": user_id,
            "job_posting_id": job_posting_id,
            "similarity_score": 0.8,
            "rule_score": 0.6,
            "overall_score": 74.0,
            "score_breakdown": {"salary_fit": 1.0, "location_fit": 0.5},
        }
        fields.update(overrides)
        match = JobMatch(**fields)
        session.add(match)
        session.commit()
        session.refresh(match)
        return match


def _get_postings() -> list[JobPosting]:
    with SyncSessionLocal() as session:
        return list(session.execute(select(JobPosting)).scalars().all())


def _get_match(match_id) -> JobMatch | None:
    with SyncSessionLocal() as session:
        return session.execute(select(JobMatch).where(JobMatch.id == match_id)).scalar_one_or_none()


def _mock_jobspy_scrape(rows: list[dict] | None = None):
    """Patch `JobSpyEnricher._scrape` on the class.

    The worker does `enricher = JobSpyEnricher(); ... enricher._scrape(...)` via
    `asyncio.to_thread`, so patching the unbound method on the class intercepts the call
    regardless of which instance invokes it. `_scrape` itself is a plain sync method (it's
    only *called* via `asyncio.to_thread`, not defined as async), so a plain `MagicMock`
    return value is correct here — no `AsyncMock` needed.
    """
    return patch(
        "app.enrichers.jobspy.JobSpyEnricher._scrape",
        return_value=list(rows if rows is not None else FAKE_JOBSPY_ROWS),
    )


def _mock_embeddings_client():
    """Patch `get_embeddings_client` at its source module.

    `_scan_jobs_for_candidate_async` does `from app.clients.embeddings import
    get_embeddings_client` *inside* the function body, executed fresh on every call — so
    patching the source attribute `app.clients.embeddings.get_embeddings_client` is
    intercepted correctly (unlike patching an already-bound local name).
    """
    mock_client = MagicMock()
    mock_client.generate_embedding = AsyncMock(
        return_value=(list(FAKE_EMBEDDING), FAKE_TOKEN_COUNT)
    )
    return patch("app.clients.embeddings.get_embeddings_client", return_value=mock_client)


def _mock_explainer(return_value: str = "This role matches your background well."):
    """Patch `generate_match_explanation` at its source module (imported locally, per-call,
    inside `_generate_explanations_for_candidate_async`)."""
    return patch(
        "app.modules.job_matching.explainer.generate_match_explanation",
        new_callable=AsyncMock,
        return_value=return_value,
    )


def _mock_enqueue_email():
    """Patch `enqueue_email` at its source module `app.workers.queue`.

    `_send_match_digest_async` does `from app.workers.queue import enqueue_email` *inside*
    the function body. That import statement re-executes on every call, resolving
    `enqueue_email` freshly from `app.workers.queue`'s namespace each time — so patching the
    source attribute (rather than any already-imported reference) is what actually gets
    picked up.
    """
    return patch("app.workers.queue.enqueue_email")


def _mock_notify_job_match(return_value: bool = True):
    """Patch `notify_job_match` at its source module `app.clients.notify`.

    Same rationale as `_mock_enqueue_email`: `_send_match_digest_async` does
    `from app.clients.notify import notify_job_match` *inside* the function body, so the
    source attribute must be patched for the re-import to pick it up.
    """
    return patch(
        "app.clients.notify.notify_job_match", new_callable=AsyncMock, return_value=return_value
    )


class TestBuildSearchTerm:
    """`_build_search_term` is a plain sync function — no async/DB needed."""

    def test_prefers_first_desired_role(self):
        prefs = MagicMock(desired_roles=["Staff Engineer", "Backend Engineer"])
        cv_doc = MagicMock(extracted_data={"current_role": "Software Engineer"})

        assert _build_search_term(prefs, cv_doc) == "Staff Engineer"

    def test_falls_back_to_cv_current_role_when_no_desired_roles(self):
        prefs = MagicMock(desired_roles=[])
        cv_doc = MagicMock(extracted_data={"current_role": "Data Scientist"})

        assert _build_search_term(prefs, cv_doc) == "Data Scientist"

    def test_falls_back_to_default_when_neither_present(self):
        prefs = MagicMock(desired_roles=[])
        cv_doc = MagicMock(extracted_data={})

        assert _build_search_term(prefs, cv_doc) == "software engineer"

    def test_falls_back_to_default_when_extracted_data_is_none(self):
        prefs = MagicMock(desired_roles=None)
        cv_doc = MagicMock(extracted_data=None)

        assert _build_search_term(prefs, cv_doc) == "software engineer"

    def test_uses_real_cvdata_current_role_field_when_present(self):
        """Regression test for the CV-parsing pipeline fix chain: `extracted_data` is now
        genuinely populated from `CVData.model_dump()` (see `document.py`'s Fix 2 wiring),
        so this locks in that `_build_search_term` reads the exact same field name
        `CVData` actually uses for "current role" — not a guessed/mismatched key.
        """
        from app.domain.candidate import CVData

        cv_data = CVData(
            full_name="Jane Doe",
            current_role="Staff Software Engineer",
            technical_skills=["Python", "SQL"],
        )
        extracted = cv_data.model_dump()
        assert "current_role" in extracted  # confirms the exact field name used below

        prefs = MagicMock(desired_roles=[])
        cv_doc = MagicMock(extracted_data=extracted)

        assert _build_search_term(prefs, cv_doc) == "Staff Software Engineer"

    def test_falls_back_to_default_when_real_cvdata_has_no_current_role(self):
        from app.domain.candidate import CVData

        cv_data = CVData(full_name="Jane Doe")  # no current_role extracted from CV
        extracted = cv_data.model_dump()

        prefs = MagicMock(desired_roles=[])
        cv_doc = MagicMock(extracted_data=extracted)

        assert _build_search_term(prefs, cv_doc) == "software engineer"


class TestScanJobsForCandidate:
    def test_end_to_end_creates_postings_and_scores(self):
        user = _create_user()
        _create_preferences(user.id)
        cv_doc = _create_completed_cv(user.id, extracted_data={"current_role": "Backend Engineer"})
        _create_cv_embedding(cv_doc.id)
        # Use dedup keys unique to this test so the shared, non-rolled-back SQLite test DB
        # (rows persist across tests in this session) can't collide with postings created
        # by other tests using the same fake title/location/source combination.
        unique_rows = [
            {**row, "title": f"{row['title']} {uuid.uuid4().hex[:8]}"} for row in FAKE_JOBSPY_ROWS
        ]

        with (
            _mock_jobspy_scrape(unique_rows),
            _mock_embeddings_client(),
            _mock_explainer(),
            _mock_enqueue_email(),
        ):
            stats = scan_jobs_for_candidate(str(user.id))

        assert stats["scraped"] == len(unique_rows)
        assert stats["new_postings"] > 0
        assert "matches_scored" in stats
        assert stats["matches_scored"] >= 0
        assert "explanations" in stats

        expected_titles = {row["title"] for row in unique_rows}
        postings = [p for p in _get_postings() if p.title in expected_titles]
        assert len(postings) == len(unique_rows)
        assert {p.title for p in postings} == expected_titles
        assert all(p.dedup_key for p in postings)

    def test_skips_embedding_when_posting_already_has_stored_embedding(self):
        """A posting scraped in this scan that already has a `JobPostingEmbedding` row
        from a prior scan must not trigger another `generate_embedding` call, and must
        not be counted in `stats["new_postings"]` (Phase 2: stop paying for duplicate
        embeddings — `has_posting_embedding` short-circuits before the OpenAI call).
        """
        user = _create_user()
        _create_preferences(user.id)
        cv_doc = _create_completed_cv(user.id, extracted_data={"current_role": "Backend Engineer"})
        _create_cv_embedding(cv_doc.id)

        unique_rows = [
            {**row, "title": f"{row['title']} {uuid.uuid4().hex[:8]}"} for row in FAKE_JOBSPY_ROWS
        ]
        already_embedded_row, fresh_row = unique_rows

        dedup_key = compute_dedup_key(
            already_embedded_row["title"], already_embedded_row["location"], "linkedin"
        )
        existing_posting = _create_posting(
            dedup_key=dedup_key,
            title=already_embedded_row["title"],
            company=already_embedded_row["company"],
            location=already_embedded_row["location"],
            remote=True,
            source="linkedin",
            sources_seen=["linkedin"],
        )
        _create_posting_embedding(existing_posting.id)

        with (
            _mock_jobspy_scrape(unique_rows),
            _mock_embeddings_client() as mock_get_client,
            _mock_explainer(),
            _mock_enqueue_email(),
        ):
            stats = scan_jobs_for_candidate(str(user.id))

        mock_client = mock_get_client.return_value
        assert mock_client.generate_embedding.call_count == 1
        called_text = mock_client.generate_embedding.call_args[0][0]
        assert fresh_row["title"] in called_text
        assert already_embedded_row["title"] not in called_text

        assert stats["scraped"] == len(unique_rows)
        assert stats["new_postings"] == 1

    def test_skips_when_preferences_missing(self):
        user = _create_user()
        _create_completed_cv(user.id, extracted_data={"current_role": "Backend Engineer"})
        postings_before = len(_get_postings())

        with _mock_jobspy_scrape() as mock_scrape, _mock_embeddings_client():
            stats = scan_jobs_for_candidate(str(user.id))

        assert stats == {"scraped": 0, "new_postings": 0, "matches_scored": 0, "explanations": 0}
        mock_scrape.assert_not_called()
        # Shared SQLite test DB has no per-test rollback (rows persist across tests in this
        # file/session), so we assert "no new postings from this call" via a before/after
        # delta rather than an absolute empty-list check.
        assert len(_get_postings()) == postings_before

    def test_skips_when_scan_disabled(self):
        user = _create_user()
        _create_preferences(user.id, is_scan_enabled=False)
        _create_completed_cv(user.id, extracted_data={"current_role": "Backend Engineer"})
        postings_before = len(_get_postings())

        with _mock_jobspy_scrape() as mock_scrape, _mock_embeddings_client():
            stats = scan_jobs_for_candidate(str(user.id))

        assert stats == {"scraped": 0, "new_postings": 0, "matches_scored": 0, "explanations": 0}
        mock_scrape.assert_not_called()
        assert len(_get_postings()) == postings_before

    def test_skips_when_no_completed_cv(self):
        user = _create_user()
        _create_preferences(user.id)
        # CV exists but is still processing — should not count as usable.
        _create_completed_cv(user.id, extracted_data={"current_role": "Backend Engineer"})
        with SyncSessionLocal() as session:
            doc = session.execute(
                select(CandidateDocument).where(CandidateDocument.user_id == user.id)
            ).scalar_one()
            doc.processing_status = "processing"
            session.commit()
        postings_before = len(_get_postings())

        with _mock_jobspy_scrape() as mock_scrape, _mock_embeddings_client():
            stats = scan_jobs_for_candidate(str(user.id))

        assert stats == {"scraped": 0, "new_postings": 0, "matches_scored": 0, "explanations": 0}
        mock_scrape.assert_not_called()
        assert len(_get_postings()) == postings_before

    def test_skips_when_no_cv_document_at_all(self):
        user = _create_user()
        _create_preferences(user.id)

        with _mock_jobspy_scrape() as mock_scrape, _mock_embeddings_client():
            stats = scan_jobs_for_candidate(str(user.id))

        assert stats == {"scraped": 0, "new_postings": 0, "matches_scored": 0, "explanations": 0}
        mock_scrape.assert_not_called()


class TestGenerateExplanationsForCandidate:
    def test_generates_and_persists_explanations(self):
        user = _create_user()
        posting = _create_posting()
        match = _create_match(user.id, posting.id, explanation=None)

        with _mock_explainer(return_value="Great fit due to matching skills and salary range."):
            result = generate_explanations_for_candidate(str(user.id))

        assert result == {"generated": 1}

        refreshed = _get_match(match.id)
        assert refreshed is not None
        assert refreshed.explanation == "Great fit due to matching skills and salary range."
        assert refreshed.explanation_generated_at is not None

    def test_continues_past_failing_match(self):
        user = _create_user()
        posting_a = _create_posting(dedup_key=uuid.uuid4().hex, title="Job A")
        posting_b = _create_posting(dedup_key=uuid.uuid4().hex, title="Job B")
        match_a = _create_match(user.id, posting_a.id, explanation=None, overall_score=90.0)
        match_b = _create_match(user.id, posting_b.id, explanation=None, overall_score=80.0)

        async def _side_effect(match, posting, settings):
            if match.id == match_a.id:
                raise ValueError("simulated explanation failure")
            return "Solid match on relevant skills."

        with patch(
            "app.modules.job_matching.explainer.generate_match_explanation",
            new_callable=AsyncMock,
            side_effect=_side_effect,
        ):
            result = generate_explanations_for_candidate(str(user.id))

        assert result == {"generated": 1}

        refreshed_a = _get_match(match_a.id)
        refreshed_b = _get_match(match_b.id)
        assert refreshed_a is not None and refreshed_a.explanation is None
        assert (
            refreshed_b is not None and refreshed_b.explanation == "Solid match on relevant skills."
        )

    def test_no_unexplained_matches_generates_nothing(self):
        user = _create_user()
        posting = _create_posting()
        _create_match(user.id, posting.id, explanation="Already explained.")

        with _mock_explainer() as mock_explain:
            result = generate_explanations_for_candidate(str(user.id))

        assert result == {"generated": 0}
        mock_explain.assert_not_called()


class TestSendMatchDigest:
    def test_sends_digest_and_marks_notified(self):
        user = _create_user(email=f"digest-{uuid.uuid4().hex[:10]}@example.com")
        _create_preferences(user.id, notification_channels=["email"])
        posting = _create_posting()
        match = _create_match(user.id, posting.id, notified_at=None)

        with _mock_enqueue_email() as mock_enqueue:
            result = send_match_digest(str(user.id))

        assert result == {"sent": 1}
        mock_enqueue.assert_called_once()
        _, kwargs = mock_enqueue.call_args
        assert kwargs["template"] == "job_match_digest"
        assert kwargs["recipient"] == user.email
        assert kwargs["context"]["matches"][0]["title"] == posting.title

        refreshed = _get_match(match.id)
        assert refreshed is not None
        assert refreshed.notified_at is not None

    def test_returns_zero_sent_when_no_unnotified_matches(self):
        user = _create_user()
        _create_preferences(user.id, notification_channels=["email"])
        posting = _create_posting()
        from datetime import UTC, datetime

        _create_match(user.id, posting.id, notified_at=datetime.now(UTC))

        with _mock_enqueue_email() as mock_enqueue:
            result = send_match_digest(str(user.id))

        assert result == {"sent": 0}
        mock_enqueue.assert_not_called()

    def test_returns_zero_sent_when_email_channel_not_enabled(self):
        user = _create_user()
        _create_preferences(user.id, notification_channels=["sms"])
        posting = _create_posting()
        _create_match(user.id, posting.id, notified_at=None)

        with _mock_enqueue_email() as mock_enqueue:
            result = send_match_digest(str(user.id))

        assert result == {"sent": 0}
        mock_enqueue.assert_not_called()

    def test_returns_zero_sent_when_preferences_missing(self):
        user = _create_user()
        posting = _create_posting()
        _create_match(user.id, posting.id, notified_at=None)

        with _mock_enqueue_email() as mock_enqueue:
            result = send_match_digest(str(user.id))

        assert result == {"sent": 0}
        mock_enqueue.assert_not_called()

    def test_calls_notify_job_match_when_webhook_channel_and_url_configured(self):
        """Webhook dispatch fires with a correctly-shaped payload when both the
        'webhook' channel is selected AND a webhook_url is configured."""
        user = _create_user(email=f"webhook-{uuid.uuid4().hex[:10]}@example.com")
        _create_preferences(
            user.id,
            notification_channels=["email", "webhook"],
            webhook_url="https://hooks.example.com/job-matches",
        )
        posting = _create_posting(source_url="https://linkedin.com/jobs/12345")
        _create_match(user.id, posting.id, notified_at=None)

        with _mock_enqueue_email(), _mock_notify_job_match(return_value=True) as mock_notify:
            result = send_match_digest(str(user.id))

        assert result == {"sent": 1}
        mock_notify.assert_called_once()
        _, kwargs = mock_notify.call_args
        assert kwargs["webhook_url"] == "https://hooks.example.com/job-matches"
        assert kwargs["candidate_id"] == str(user.id)
        assert kwargs["matches"][0]["title"] == posting.title
        assert kwargs["matches"][0]["company"] == posting.company
        assert kwargs["matches"][0]["source_url"] == posting.source_url

    def test_skips_notify_job_match_when_webhook_channel_not_selected(self):
        """No webhook_url is dispatched to when 'webhook' isn't in notification_channels,
        even though a webhook_url is configured."""
        user = _create_user(email=f"webhook-{uuid.uuid4().hex[:10]}@example.com")
        _create_preferences(
            user.id,
            notification_channels=["email"],
            webhook_url="https://hooks.example.com/job-matches",
        )
        posting = _create_posting()
        _create_match(user.id, posting.id, notified_at=None)

        with _mock_enqueue_email(), _mock_notify_job_match() as mock_notify:
            result = send_match_digest(str(user.id))

        assert result == {"sent": 1}
        mock_notify.assert_not_called()

    def test_skips_notify_job_match_when_webhook_url_not_configured(self):
        """No dispatch when 'webhook' is selected but no webhook_url is configured."""
        user = _create_user(email=f"webhook-{uuid.uuid4().hex[:10]}@example.com")
        _create_preferences(
            user.id,
            notification_channels=["email", "webhook"],
            webhook_url=None,
        )
        posting = _create_posting()
        _create_match(user.id, posting.id, notified_at=None)

        with _mock_enqueue_email(), _mock_notify_job_match() as mock_notify:
            result = send_match_digest(str(user.id))

        assert result == {"sent": 1}
        mock_notify.assert_not_called()

    def test_webhook_failure_is_fail_soft_and_still_marks_notified(self):
        """A failed webhook POST (notify_job_match returns False) must not raise and
        must not prevent the digest from completing / marking matches notified."""
        user = _create_user(email=f"webhook-{uuid.uuid4().hex[:10]}@example.com")
        _create_preferences(
            user.id,
            notification_channels=["email", "webhook"],
            webhook_url="https://hooks.example.com/job-matches",
        )
        posting = _create_posting()
        match = _create_match(user.id, posting.id, notified_at=None)

        with _mock_enqueue_email(), _mock_notify_job_match(return_value=False) as mock_notify:
            result = send_match_digest(str(user.id))

        assert result == {"sent": 1}
        mock_notify.assert_called_once()

        refreshed = _get_match(match.id)
        assert refreshed is not None
        assert refreshed.notified_at is not None


class TestCheckWorkerHealth:
    def test_returns_true_when_redis_and_queue_are_healthy(self):
        """`fake_redis` (autouse) monkeypatches `get_redis_connection` to return a
        `FakeRedis`, and monkeypatches `rq.Queue` to `FakeQueue` — but `FakeQueue` has no
        `__len__`, so `len(queue)` in `check_worker_health` raises `TypeError` and the
        function's `except Exception` swallows it into a `False` return. That means relying
        on the bare autouse `fake_redis` fixture here would actually assert the *false*
        path, not the true path the health check is meant to exercise. We patch explicitly
        instead to simulate a genuinely healthy Redis + queue."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_queue = MagicMock()
        mock_queue.__len__.return_value = 0

        with (
            patch("app.workers.queue.get_redis_connection", return_value=mock_redis),
            patch("rq.Queue", return_value=mock_queue),
        ):
            assert check_worker_health("job_matching") is True
        mock_redis.ping.assert_called_once()

    def test_returns_false_on_redis_connection_error(self):
        def _raise(*args, **kwargs):
            raise ConnectionError("could not connect to redis")

        with patch("app.workers.queue.get_redis_connection", side_effect=_raise):
            assert check_worker_health("job_matching") is False

    def test_returns_false_with_bare_fake_redis_due_to_fakequeue_len_gap(self, fake_redis):
        """Documents the real, current behavior of the autouse `fake_redis` fixture for this
        health check: it returns False (see explanation above), not True. If `FakeQueue`
        ever grows a `__len__`, this test should be revisited alongside
        `test_returns_true_when_redis_and_queue_are_healthy`."""
        assert check_worker_health("job_matching") is False


class TestFanOutDailyScans:
    """`rq_scheduler` is not installed in this test environment (it's a lazy import inside
    `_fan_out_daily_scans_async`, and no other test in this suite exercises that import path),
    so we inject a fake module via `sys.modules` rather than skipping this test entirely.
    """

    def test_scheduler_is_constructed_with_job_matching_queue_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression test for a real bug: `Scheduler.enqueue_at()` (unlike `Scheduler.cron()`,
        which takes `queue_name` per-call) always enqueues into the `Scheduler` instance's own
        configured queue. Constructing `Scheduler(connection=...)` without `queue_name=` means
        every staggered scan job silently lands in rq_scheduler's "default" queue instead of
        "job_matching" — and `worker-job-matching` (which only listens to "job_matching") would
        never process them. This test locks in the fix: `queue_name=QUEUE_JOB_MATCHING` must be
        passed to the `Scheduler` constructor.
        """
        user = _create_user()
        _create_preferences(user.id, is_scan_enabled=True)

        captured_kwargs: dict[str, object] = {}

        class _FakeScheduler:
            def __init__(self, **kwargs: object) -> None:
                captured_kwargs.update(kwargs)

            def enqueue_at(self, *args: object, **kwargs: object) -> None:
                return None

        fake_rq_scheduler_module = MagicMock()
        fake_rq_scheduler_module.Scheduler = _FakeScheduler
        monkeypatch.setitem(sys.modules, "rq_scheduler", fake_rq_scheduler_module)

        result = fan_out_daily_scans()

        assert captured_kwargs.get("queue_name") == "job_matching"
        assert result["enqueued"] >= 1
