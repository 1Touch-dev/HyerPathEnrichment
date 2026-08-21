"""Tests for the swipe deck. Fakes Module 1's job_matches/job_postings rows directly per §4.1 —
these tests do not require Module 1's worker/scanner to run."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.auth.models import User
from app.core.config import get_settings
from app.modules.job_matching.models import (  # Module 1 — see §4.1 dependency note
    JobMatch,
    JobPosting,
    JobPostingEmbedding,
)
from app.modules.job_swipe import repository
from app.modules.job_swipe.schemas import SwipeActionRequest
from app.modules.job_swipe.service import JobSwipeService
from app.modules.manual_jobs.models import ManualJobEntry


@pytest.fixture
async def test_user(db):
    user = User(
        id=uuid4(),
        email=f"swipe-{uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def other_user(db):
    user = User(
        id=uuid4(),
        email=f"swipe-other-{uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def seeded_match(db, test_user):
    posting = JobPosting(
        id=uuid4(),
        dedup_key=f"hash-{uuid4().hex}",
        title="Backend Engineer",
        company="Acme",
        location="Remote",
        remote=True,
        source="linkedin",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        sources_seen=["linkedin"],
        is_active=True,
    )
    db.add(posting)
    await db.flush()
    match = JobMatch(
        id=uuid4(),
        user_id=test_user.id,
        job_posting_id=posting.id,
        similarity_score=0.8,
        rule_score=1.0,
        overall_score=86.0,
        score_breakdown={},
    )
    db.add(match)
    await db.commit()
    return match, posting


async def test_get_deck_returns_unswiped_matches(db, test_user, seeded_match):
    service = JobSwipeService(db)
    deck = await service.get_deck(test_user.id)
    assert len(deck.cards) == 1
    assert deck.cards[0].company == "Acme"


async def test_get_deck_empty_for_user_with_no_matches(db, test_user):
    service = JobSwipeService(db)
    deck = await service.get_deck(test_user.id)
    assert deck.cards == []
    assert deck.has_more is False


async def test_get_deck_excludes_manual_entries_with_no_crash(db, test_user):
    """Regression test (Module F, §10.6/§10.7): a manual entry (job_posting_id NULL,
    manual_job_entry_id set) is added straight to the tracker, bypassing swipe-to-match
    entirely — it must never appear in the swipe deck, and the deck query (previously an
    inner join on JobPosting) must not raise when a manual-entry row exists for the user.
    """
    entry = ManualJobEntry(
        id=uuid4(),
        user_id=test_user.id,
        title="Self-Sourced Role",
        company="Referral Co",
    )
    db.add(entry)
    await db.flush()
    manual_match = JobMatch(
        id=uuid4(),
        user_id=test_user.id,
        job_posting_id=None,
        manual_job_entry_id=entry.id,
        similarity_score=0.0,
        rule_score=0.0,
        overall_score=999.0,  # would sort first if it leaked into the deck
        score_breakdown={},
        application_status="new",
    )
    db.add(manual_match)
    await db.commit()

    service = JobSwipeService(db)
    deck = await service.get_deck(test_user.id)

    assert str(manual_match.id) not in {card.match_id for card in deck.cards}
    assert deck.cards == []


async def test_get_deck_flags_below_similarity_threshold_matches(db, test_user):
    """Module A (§5.5): SwipeableMatchResponse.below_similarity_threshold surfaces the
    similarity-fallback flag from JobMatch.score_breakdown."""
    service = JobSwipeService(db)

    flagged_match, _ = await _make_match(
        db,
        test_user,
        50.0,
        title="Fallback Job",
        score_breakdown={"below_similarity_threshold": True},
    )
    unflagged_match, _ = await _make_match(
        db,
        test_user,
        50.0,
        title="Strict Job",
        score_breakdown={"below_similarity_threshold": False},
    )
    no_key_match, _ = await _make_match(
        db,
        test_user,
        50.0,
        title="No Key Job",
        score_breakdown={},
    )

    deck = await service.get_deck(test_user.id)
    cards_by_match_id = {card.match_id: card for card in deck.cards}

    assert cards_by_match_id[str(flagged_match.id)].below_similarity_threshold is True
    assert cards_by_match_id[str(unflagged_match.id)].below_similarity_threshold is False
    assert cards_by_match_id[str(no_key_match.id)].below_similarity_threshold is False


async def test_swipe_removes_card_from_next_deck_fetch(db, test_user, seeded_match):
    match, _ = seeded_match
    service = JobSwipeService(db)
    await service.swipe(test_user.id, str(match.id), SwipeActionRequest(direction="right"))

    deck = await service.get_deck(test_user.id)
    assert len(deck.cards) == 0


async def test_swipe_overwrites_previous_decision_not_duplicate(db, test_user, seeded_match):
    match, _ = seeded_match
    service = JobSwipeService(db)
    first = await service.swipe(test_user.id, str(match.id), SwipeActionRequest(direction="left"))
    second = await service.swipe(test_user.id, str(match.id), SwipeActionRequest(direction="right"))
    assert first.match_id == second.match_id
    assert second.direction == "right"


async def test_swipe_accepts_up_direction_for_super_like(db, test_user, seeded_match):
    match, _ = seeded_match
    service = JobSwipeService(db)
    result = await service.swipe(test_user.id, str(match.id), SwipeActionRequest(direction="up"))
    assert result.direction == "up"


async def test_swipe_rejects_match_owned_by_another_user(db, test_user, other_user, seeded_match):
    match, _ = seeded_match
    service = JobSwipeService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.swipe(other_user.id, str(match.id), SwipeActionRequest(direction="right"))
    assert exc_info.value.status_code == 404


async def test_swipe_rejects_unknown_match_id(db, test_user):
    service = JobSwipeService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.swipe(test_user.id, str(uuid4()), SwipeActionRequest(direction="right"))
    assert exc_info.value.status_code == 404


def test_swipe_action_request_rejects_invalid_direction():
    with pytest.raises(ValidationError):
        SwipeActionRequest(direction="sideways")


async def _make_match(
    db,
    user,
    overall_score: float,
    *,
    title: str = "Job",
    score_breakdown: dict | None = None,
) -> tuple[JobMatch, JobPosting]:
    posting = JobPosting(
        id=uuid4(),
        dedup_key=f"hash-{uuid4().hex}",
        title=title,
        company="Acme",
        location="Remote",
        remote=True,
        source="linkedin",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        sources_seen=["linkedin"],
        is_active=True,
    )
    db.add(posting)
    await db.flush()
    match = JobMatch(
        id=uuid4(),
        user_id=user.id,
        job_posting_id=posting.id,
        similarity_score=0.8,
        rule_score=1.0,
        overall_score=overall_score,
        score_breakdown=score_breakdown if score_breakdown is not None else {},
    )
    db.add(match)
    await db.commit()
    return match, posting


_EMBEDDING_DIM = 1536  # JobPostingEmbedding.embedding is pgvector Vector(1536) on Postgres;
# SQLite doesn't enforce vector length, so a short test vector only surfaces there. Zero-padding
# preserves cosine similarity exactly (padding contributes 0 to both dot product and magnitude),
# so this keeps the tests' short, readable vectors while still satisfying Postgres's dimension check.


def _padded(vector: list[float]) -> list[float]:
    return vector + [0.0] * (_EMBEDDING_DIM - len(vector))


async def _add_embedding(db, posting: JobPosting, vector: list[float]) -> None:
    embedding = JobPostingEmbedding(job_posting_id=posting.id, token_count=10)
    embedding.embedding = _padded(vector)
    db.add(embedding)
    await db.commit()


async def test_swipe_right_boosts_similar_posting_above_dissimilar_one(db, test_user):
    """Swiping right on a posting should re-rank a near-identical-embedding posting above a
    near-orthogonal one in the next deck fetch, even though both start with the same
    overall_score (isolates the similarity boost from the base-score ordering)."""
    service = JobSwipeService(db)

    liked_match, liked_posting = await _make_match(db, test_user, 50.0, title="Liked Job")
    similar_match, similar_posting = await _make_match(db, test_user, 50.0, title="Similar Job")
    dissimilar_match, dissimilar_posting = await _make_match(
        db, test_user, 50.0, title="Dissimilar Job"
    )

    liked_vector = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    similar_vector = [0.99, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    dissimilar_vector = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    await _add_embedding(db, liked_posting, liked_vector)
    await _add_embedding(db, similar_posting, similar_vector)
    await _add_embedding(db, dissimilar_posting, dissimilar_vector)

    await service.swipe(test_user.id, str(liked_match.id), SwipeActionRequest(direction="right"))

    deck = await service.get_deck(test_user.id)
    match_ids_in_order = [card.match_id for card in deck.cards]

    # liked_match was swiped, so it should no longer appear.
    assert str(liked_match.id) not in match_ids_in_order
    assert str(similar_match.id) in match_ids_in_order
    assert str(dissimilar_match.id) in match_ids_in_order

    similar_rank = match_ids_in_order.index(str(similar_match.id))
    dissimilar_rank = match_ids_in_order.index(str(dissimilar_match.id))
    assert similar_rank < dissimilar_rank


async def test_compute_similarity_boosts_falls_back_to_python_when_pgvector_query_raises(
    db, test_user, monkeypatch
):
    """Deterministic proof of the fallback branch in repository.py's
    _compute_similarity_boosts (lines 94-101), without needing real Postgres.

    Monkeypatches the `get_settings` name imported *inside* repository.py (not the
    global `app.core.config.get_settings`, which the `db` fixture's session still
    relies on to stay SQLite-backed) so `_compute_similarity_boosts` believes it's
    talking to Postgres and takes the `is_postgres` branch. It then issues the raw
    pgvector `<=>`/`::vector` SQL against the test session's real SQLite connection,
    which doesn't understand that syntax and raises — exercising the `except
    Exception` handler that falls through to the Python `cosine_similarity()` path.
    """
    fake_settings = SimpleNamespace(database_url="postgresql+asyncpg://fake-host/fake-db")
    monkeypatch.setattr(repository, "get_settings", lambda: fake_settings)

    service = JobSwipeService(db)

    liked_match, liked_posting = await _make_match(db, test_user, 50.0, title="Liked Job")
    similar_match, similar_posting = await _make_match(db, test_user, 50.0, title="Similar Job")
    dissimilar_match, dissimilar_posting = await _make_match(
        db, test_user, 50.0, title="Dissimilar Job"
    )

    liked_vector = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    similar_vector = [0.99, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    dissimilar_vector = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    await _add_embedding(db, liked_posting, liked_vector)
    await _add_embedding(db, similar_posting, similar_vector)
    await _add_embedding(db, dissimilar_posting, dissimilar_vector)

    await service.swipe(test_user.id, str(liked_match.id), SwipeActionRequest(direction="right"))

    deck = await service.get_deck(test_user.id)
    match_ids_in_order = [card.match_id for card in deck.cards]

    # liked_match was swiped, so it should no longer appear.
    assert str(liked_match.id) not in match_ids_in_order
    assert str(similar_match.id) in match_ids_in_order
    assert str(dissimilar_match.id) in match_ids_in_order

    similar_rank = match_ids_in_order.index(str(similar_match.id))
    dissimilar_rank = match_ids_in_order.index(str(dissimilar_match.id))
    assert similar_rank < dissimilar_rank


@pytest.mark.postgres
async def test_swipe_right_boosts_similar_posting_above_dissimilar_one_on_real_postgres(
    db, test_user
):
    """Real-Postgres proof that the pgvector `<=>` SQL branch in
    _compute_similarity_boosts (not just its SQLite/error fallback) produces the
    correct ranking. Same scenario/assertions as
    test_swipe_right_boosts_similar_posting_above_dissimilar_one above.

    NOTE on the two coexisting "postgres opt-in" conventions in this suite:
    test_alembic_migrations.py's `@pytest.mark.postgres` tests read `TEST_DATABASE_URL`
    and drive a separate sync raw engine just for that one test. This test uses a
    *different* convention: conftest.py (lines 9-24) detects `DATABASE_URL` itself
    being a `postgresql://` URL at pytest startup and switches the *entire* session —
    including the async `db`/`test_user` fixtures used here — over to real Postgres.
    Don't confuse the two; this test's runtime skip below checks `DATABASE_URL` (via
    `get_settings().database_url`), not `TEST_DATABASE_URL`.
    """
    if "postgresql" not in get_settings().database_url.lower():
        pytest.skip("Requires DATABASE_URL pointed at real Postgres with pgvector")

    service = JobSwipeService(db)

    liked_match, liked_posting = await _make_match(db, test_user, 50.0, title="Liked Job")
    similar_match, similar_posting = await _make_match(db, test_user, 50.0, title="Similar Job")
    dissimilar_match, dissimilar_posting = await _make_match(
        db, test_user, 50.0, title="Dissimilar Job"
    )

    liked_vector = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    similar_vector = [0.99, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    dissimilar_vector = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    await _add_embedding(db, liked_posting, liked_vector)
    await _add_embedding(db, similar_posting, similar_vector)
    await _add_embedding(db, dissimilar_posting, dissimilar_vector)

    await service.swipe(test_user.id, str(liked_match.id), SwipeActionRequest(direction="right"))

    deck = await service.get_deck(test_user.id)
    match_ids_in_order = [card.match_id for card in deck.cards]

    # liked_match was swiped, so it should no longer appear.
    assert str(liked_match.id) not in match_ids_in_order
    assert str(similar_match.id) in match_ids_in_order
    assert str(dissimilar_match.id) in match_ids_in_order

    similar_rank = match_ids_in_order.index(str(similar_match.id))
    dissimilar_rank = match_ids_in_order.index(str(dissimilar_match.id))
    assert similar_rank < dissimilar_rank


async def test_undo_last_swipe_restores_card_to_next_deck_fetch(db, test_user, seeded_match):
    match, _ = seeded_match
    service = JobSwipeService(db)

    await service.swipe(test_user.id, str(match.id), SwipeActionRequest(direction="right"))
    deck_after_swipe = await service.get_deck(test_user.id)
    assert len(deck_after_swipe.cards) == 0

    result = await service.undo_last_swipe(test_user.id)
    assert result.match_id == str(match.id)
    assert result.direction == "right"

    deck_after_undo = await service.get_deck(test_user.id)
    assert len(deck_after_undo.cards) == 1
    assert deck_after_undo.cards[0].match_id == str(match.id)


async def test_undo_last_swipe_raises_404_when_no_prior_swipes(db, test_user):
    service = JobSwipeService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.undo_last_swipe(test_user.id)
    assert exc_info.value.status_code == 404
