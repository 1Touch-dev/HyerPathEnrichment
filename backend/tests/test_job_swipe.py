"""Tests for the swipe deck. Fakes Module 1's job_matches/job_postings rows directly per §4.1 —
these tests do not require Module 1's worker/scanner to run."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.auth.models import User
from app.modules.job_matching.models import (  # Module 1 — see §4.1 dependency note
    JobMatch,
    JobPosting,
)
from app.modules.job_swipe.schemas import SwipeActionRequest
from app.modules.job_swipe.service import JobSwipeService


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
