"""Paywall tests — server-side blur must strip real enriched text from JSON."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.password import hash_password
from app.core.config import get_settings
from app.modules.billing import repository, service
from app.modules.billing.service import MATCH_EXPLANATION_TEASER
from app.modules.job_matching.models import JobMatch, JobPosting
from tests.envelope_helpers import assert_success


def _enable_billing(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_billing", True)
    monkeypatch.setattr(settings, "stripe_secret_key", SecretStr("sk_test_x"))
    monkeypatch.setattr(settings, "stripe_webhook_secret", SecretStr("whsec_test"))
    monkeypatch.setattr(settings, "stripe_price_id_premium", "price_test")


def _headers(user_id) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.api_token}",
        "X-Test-User-ID": str(user_id),
    }


@pytest.fixture
async def paywall_user(db: AsyncSession) -> User:
    user = User(
        email=f"paywall-{uuid4().hex[:8]}@example.com",
        first_name="Free",
        last_name="Candidate",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def explained_match(db: AsyncSession, paywall_user: User) -> JobMatch:
    posting = JobPosting(
        id=uuid4(),
        dedup_key=f"dedup-{uuid4().hex}",
        title="Staff Engineer",
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

    secret_explanation = "SECRET: You match because of your Rust experience and leadership."
    match = JobMatch(
        id=uuid4(),
        user_id=paywall_user.id,
        job_posting_id=posting.id,
        similarity_score=0.9,
        rule_score=1.0,
        overall_score=92.0,
        score_breakdown={},
        explanation=secret_explanation,
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)
    match._secret_explanation = secret_explanation  # type: ignore[attr-defined]
    return match


@pytest.mark.asyncio
async def test_free_user_gets_blurred_match_without_real_explanation(
    client: TestClient,
    paywall_user: User,
    explained_match: JobMatch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_billing(monkeypatch)

    data = assert_success(
        client.get("/api/job-matching/matches", headers=_headers(paywall_user.id))
    )
    assert len(data["matches"]) == 1
    match = data["matches"][0]
    assert match["is_blurred"] is True
    assert match["explanation"] == MATCH_EXPLANATION_TEASER
    assert "SECRET" not in match["explanation"]
    assert explained_match.explanation not in str(data)


@pytest.mark.asyncio
async def test_premium_user_gets_full_explanation(
    client: TestClient,
    paywall_user: User,
    explained_match: JobMatch,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_billing(monkeypatch)

    await repository.create_subscription(
        db,
        user_id=paywall_user.id,
        stripe_customer_id=f"cus_{uuid4().hex[:8]}",
        stripe_subscription_id=f"sub_{uuid4().hex[:8]}",
        plan_tier="premium",
        status="active",
    )

    data = assert_success(
        client.get("/api/job-matching/matches", headers=_headers(paywall_user.id))
    )
    match = data["matches"][0]
    assert match["is_blurred"] is False
    assert match["explanation"] == explained_match.explanation


@pytest.mark.asyncio
async def test_canceled_subscription_reverts_to_blurred(
    client: TestClient,
    paywall_user: User,
    explained_match: JobMatch,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_billing(monkeypatch)

    sub = await repository.create_subscription(
        db,
        user_id=paywall_user.id,
        stripe_customer_id=f"cus_{uuid4().hex[:8]}",
        stripe_subscription_id=f"sub_{uuid4().hex[:8]}",
        plan_tier="premium",
        status="active",
    )
    await repository.update_subscription(db, sub, status="canceled", plan_tier="free")

    tier = await service.get_effective_tier(db, paywall_user.id)
    assert tier == "free"

    data = assert_success(
        client.get("/api/job-matching/matches", headers=_headers(paywall_user.id))
    )
    assert data["matches"][0]["is_blurred"] is True


@pytest.mark.asyncio
async def test_free_user_swipe_deck_blurs_explanation(
    client: TestClient,
    paywall_user: User,
    explained_match: JobMatch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_billing(monkeypatch)

    data = assert_success(client.get("/api/matches/swipe-deck", headers=_headers(paywall_user.id)))
    assert len(data["cards"]) == 1
    card = data["cards"][0]
    assert card["is_blurred"] is True
    assert card["explanation"] == MATCH_EXPLANATION_TEASER
    assert "SECRET" not in card["explanation"]
    assert explained_match.explanation not in str(data)


@pytest.mark.asyncio
async def test_premium_user_swipe_deck_full_explanation(
    client: TestClient,
    paywall_user: User,
    explained_match: JobMatch,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_billing(monkeypatch)
    await repository.create_subscription(
        db,
        user_id=paywall_user.id,
        stripe_customer_id=f"cus_{uuid4().hex[:8]}",
        stripe_subscription_id=f"sub_{uuid4().hex[:8]}",
        plan_tier="premium",
        status="active",
    )

    data = assert_success(client.get("/api/matches/swipe-deck", headers=_headers(paywall_user.id)))
    card = data["cards"][0]
    assert card["is_blurred"] is False
    assert card["explanation"] == explained_match.explanation


@pytest.mark.asyncio
async def test_free_user_cv_feedback_blurs_enriched_fields(
    client: TestClient,
    paywall_user: User,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.billing.service import (
        CV_IMPROVEMENTS_TEASER,
        CV_METHODOLOGY_TEASER,
        CV_STRENGTHS_TEASER,
    )
    from app.modules.documents.models import CandidateDocument, CvFeedbackReport

    _enable_billing(monkeypatch)

    secret_strength = "SECRET_STRENGTH: deep systems design experience"
    secret_improvement = "SECRET_IMPROVEMENT: quantify impact with metrics"
    secret_bullet = {
        "original": "Did work",
        "rewritten": "SECRET_BULLET: Led migration cutting latency 40%",
        "rationale": "SECRET_RATIONALE: adds measurable outcome",
    }

    doc = CandidateDocument(
        id=uuid4(),
        user_id=paywall_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path=f"documents/{paywall_user.id}/cv.pdf",
        file_hash=f"hash-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        extracted_data={"email": "jane@example.com"},
        processing_status="completed",
    )
    db.add(doc)
    await db.flush()

    report = CvFeedbackReport(
        id=uuid4(),
        document_id=doc.id,
        user_id=paywall_user.id,
        target_role="Backend Engineer",
        ats_score=70,
        strengths=[secret_strength],
        improvements=[secret_improvement],
        rewritten_bullets=[secret_bullet],
        accepted_bullet_indices=[],
    )
    db.add(report)
    await db.commit()

    data = assert_success(
        client.get(f"/api/documents/{doc.id}/feedback", headers=_headers(paywall_user.id))
    )
    assert data["is_blurred"] is True
    assert data["strengths"] == CV_STRENGTHS_TEASER
    assert data["improvements"] == CV_IMPROVEMENTS_TEASER
    assert data["rewritten_bullets"] == []
    assert data["ats_score_methodology"] == CV_METHODOLOGY_TEASER
    raw = str(data)
    assert "SECRET_STRENGTH" not in raw
    assert "SECRET_IMPROVEMENT" not in raw
    assert "SECRET_BULLET" not in raw
    assert "SECRET_RATIONALE" not in raw


@pytest.mark.asyncio
async def test_premium_user_cv_feedback_full_content(
    client: TestClient,
    paywall_user: User,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.documents.models import CandidateDocument, CvFeedbackReport

    _enable_billing(monkeypatch)
    await repository.create_subscription(
        db,
        user_id=paywall_user.id,
        stripe_customer_id=f"cus_{uuid4().hex[:8]}",
        stripe_subscription_id=f"sub_{uuid4().hex[:8]}",
        plan_tier="premium",
        status="active",
    )

    secret_strength = "SECRET_STRENGTH: deep systems design experience"
    doc = CandidateDocument(
        id=uuid4(),
        user_id=paywall_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path=f"documents/{paywall_user.id}/cv.pdf",
        file_hash=f"hash-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        extracted_data={"email": "jane@example.com"},
        processing_status="completed",
    )
    db.add(doc)
    await db.flush()

    report = CvFeedbackReport(
        id=uuid4(),
        document_id=doc.id,
        user_id=paywall_user.id,
        target_role="Backend Engineer",
        ats_score=70,
        strengths=[secret_strength],
        improvements=["Add metrics"],
        rewritten_bullets=[
            {"original": "Did work", "rewritten": "Did great work", "rationale": "clarity"}
        ],
        accepted_bullet_indices=[],
    )
    db.add(report)
    await db.commit()

    data = assert_success(
        client.get(f"/api/documents/{doc.id}/feedback", headers=_headers(paywall_user.id))
    )
    assert data["is_blurred"] is False
    assert data["strengths"] == [secret_strength]
    assert len(data["rewritten_bullets"]) == 1
