"""End-to-end API tests for every new Module 2 route, via FastAPI's TestClient.

Covers: status codes, auth enforcement (401 without cookie), and response envelope shape
(every success response wrapped by EnvelopeAPIRoute per the existing convention).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.main import app
from app.modules.documents.models import CandidateDocument
from app.modules.job_matching.models import JobMatch, JobPosting
from app.modules.portfolio.models import PortfolioProfile
from tests.envelope_helpers import assert_error, assert_success


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _auth_headers(user_id: str | None = None) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.api_token}",
        "X-Test-User-ID": user_id or str(uuid4()),
    }


@pytest.fixture
async def completed_document(db: AsyncSession) -> dict[str, Any]:
    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"api-doc-{user_id.hex[:8]}@example.com",
        first_name="Api",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)

    doc = CandidateDocument(
        id=uuid4(),
        user_id=user_id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"hash-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe, Software Engineer",
        extracted_data={"email": "jane@example.com"},
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return {"user_id": user_id, "document": doc}


@pytest.fixture
async def seeded_match(db: AsyncSession) -> dict[str, Any]:
    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"api-match-{user_id.hex[:8]}@example.com",
        first_name="Api",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)

    posting = JobPosting(
        id=uuid4(),
        dedup_key=f"dedup-{uuid4().hex}",
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
        user_id=user_id,
        job_posting_id=posting.id,
        similarity_score=0.8,
        rule_score=1.0,
        overall_score=86.0,
        score_breakdown={},
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return {"user_id": user_id, "match": match, "posting": posting}


@pytest.fixture
async def published_portfolio(db: AsyncSession) -> PortfolioProfile:
    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"api-portfolio-{user_id.hex[:8]}@example.com",
        first_name="Api",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)

    profile = PortfolioProfile(
        id=uuid4(),
        user_id=user_id,
        slug=f"api-slug-{uuid4().hex[:8]}",
        display_name="Api User",
        headline="Backend Engineer",
        is_published=True,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# CV completeness / CV chat / CV feedback
# ---------------------------------------------------------------------------


def test_completeness_route_requires_auth(client: TestClient) -> None:
    response = client.get("/api/documents/00000000-0000-0000-0000-000000000000/completeness")
    assert_error(response, 401)


def test_completeness_route_returns_envelope_shape(
    client: TestClient, completed_document: dict[str, Any]
) -> None:
    doc = completed_document["document"]
    headers = _auth_headers(str(completed_document["user_id"]))
    response = client.get(f"/api/documents/{doc.id}/completeness", headers=headers)
    data = assert_success(response)
    assert "completeness_score" in data
    assert "missing_fields" in data


def test_cv_chat_start_session_route(
    client: TestClient, completed_document: dict[str, Any]
) -> None:
    doc = completed_document["document"]
    headers = _auth_headers(str(completed_document["user_id"]))
    response = client.post(f"/api/documents/{doc.id}/cv-chat/sessions", headers=headers)
    data = assert_success(response)
    assert data["status"] == "active"


def test_cv_feedback_request_route_returns_job_id(
    client: TestClient, completed_document: dict[str, Any]
) -> None:
    doc = completed_document["document"]
    headers = _auth_headers(str(completed_document["user_id"]))
    response = client.post(
        f"/api/documents/{doc.id}/feedback",
        headers=headers,
        json={"target_role": "Backend Engineer"},
    )
    data = assert_success(response)
    assert "job_id" in data


def test_cv_chat_post_message_route(client: TestClient, completed_document: dict[str, Any]) -> None:
    doc = completed_document["document"]
    headers = _auth_headers(str(completed_document["user_id"]))
    start_response = client.post(f"/api/documents/{doc.id}/cv-chat/sessions", headers=headers)
    session_id = assert_success(start_response)["session_id"]

    response = client.post(
        f"/api/documents/cv-chat/sessions/{session_id}/messages",
        headers=headers,
        json={"content": "555-0100"},
    )
    data = assert_success(response)
    assert "assistant_message" in data
    assert "session" in data


def test_cv_feedback_get_route_404_when_no_report(
    client: TestClient, completed_document: dict[str, Any]
) -> None:
    doc = completed_document["document"]
    headers = _auth_headers(str(completed_document["user_id"]))
    response = client.get(f"/api/documents/{doc.id}/feedback", headers=headers)
    assert_error(response, 404)


async def test_cv_feedback_accept_bullet_route(
    client: TestClient, completed_document: dict[str, Any], db: AsyncSession
) -> None:
    from app.modules.documents.models import CvFeedbackReport

    doc = completed_document["document"]
    report = CvFeedbackReport(
        id=uuid4(),
        document_id=doc.id,
        user_id=completed_document["user_id"],
        target_role="Backend Engineer",
        ats_score=70,
        strengths=["Strong background"],
        improvements=["Add metrics"],
        rewritten_bullets=[
            {"original": "Did work", "rewritten": "Did great work", "rationale": "clarity"}
        ],
        accepted_bullet_indices=[],
    )
    db.add(report)
    await db.commit()

    headers = _auth_headers(str(completed_document["user_id"]))
    response = client.post(
        f"/api/documents/{doc.id}/feedback/{report.id}/accept",
        headers=headers,
        json={"bullet_index": 0},
    )
    data = assert_success(response)
    assert data["accepted_bullet_indices"] == [0]


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


def test_portfolio_profile_put_route_requires_auth(client: TestClient) -> None:
    response = client.put("/api/portfolio/profile", json={"slug": "test-slug"})
    assert_error(response, 401)


def test_portfolio_profile_put_route_success(client: TestClient) -> None:
    headers = _auth_headers()
    response = client.put(
        "/api/portfolio/profile",
        headers=headers,
        json={"slug": "my-new-slug", "is_published": True},
    )
    data = assert_success(response)
    assert data["slug"] == "my-new-slug"


def test_portfolio_public_route_is_unauthenticated(
    client: TestClient, published_portfolio: PortfolioProfile
) -> None:
    response = client.get(f"/api/portfolio/public/{published_portfolio.slug}")
    data = assert_success(response)
    assert data["slug"] == published_portfolio.slug


def test_portfolio_public_route_404_for_unknown_slug(client: TestClient) -> None:
    response = client.get("/api/portfolio/public/does-not-exist")
    assert_error(response, 404)


def test_portfolio_get_my_profile_route(client: TestClient) -> None:
    headers = _auth_headers()
    client.put("/api/portfolio/profile", headers=headers, json={"slug": "my-get-profile-slug"})

    response = client.get("/api/portfolio/profile", headers=headers)
    data = assert_success(response)
    assert data["slug"] == "my-get-profile-slug"


def test_portfolio_add_item_route(client: TestClient) -> None:
    headers = _auth_headers()
    client.put("/api/portfolio/profile", headers=headers, json={"slug": "has-portfolio-items"})

    response = client.post(
        "/api/portfolio/items",
        headers=headers,
        json={"item_type": "github", "title": "My Project", "url": "https://github.com/x/y"},
    )
    data = assert_success(response, status=201)
    assert data["title"] == "My Project"


def test_portfolio_delete_item_route(client: TestClient) -> None:
    headers = _auth_headers()
    client.put(
        "/api/portfolio/profile", headers=headers, json={"slug": "deletable-portfolio-items"}
    )
    item_response = client.post(
        "/api/portfolio/items",
        headers=headers,
        json={"item_type": "live_demo", "title": "Demo", "url": "https://example.com"},
    )
    item_id = assert_success(item_response, status=201)["item_id"]

    response = client.delete(f"/api/portfolio/items/{item_id}", headers=headers)
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# Job swipe
# ---------------------------------------------------------------------------


def test_swipe_deck_route_requires_auth(client: TestClient) -> None:
    response = client.get("/api/matches/swipe-deck")
    assert_error(response, 401)


def test_swipe_deck_route_returns_cards(client: TestClient, seeded_match: dict[str, Any]) -> None:
    headers = _auth_headers(str(seeded_match["user_id"]))
    response = client.get("/api/matches/swipe-deck", headers=headers)
    data = assert_success(response)
    assert isinstance(data["cards"], list)
    assert len(data["cards"]) == 1


def test_swipe_action_route(client: TestClient, seeded_match: dict[str, Any]) -> None:
    match = seeded_match["match"]
    headers = _auth_headers(str(seeded_match["user_id"]))
    response = client.post(
        f"/api/matches/{match.id}/swipe", headers=headers, json={"direction": "up"}
    )
    data = assert_success(response)
    assert data["direction"] == "up"


# ---------------------------------------------------------------------------
# Outreach
# ---------------------------------------------------------------------------


def test_outreach_draft_route_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/outreach/drafts", json={"company_name": "Acme", "document_id": "x"}
    )
    assert_error(response, 401)


def test_outreach_draft_route_returns_job_reference(
    client: TestClient, completed_document: dict[str, Any]
) -> None:
    doc = completed_document["document"]
    headers = _auth_headers(str(completed_document["user_id"]))
    response = client.post(
        "/api/outreach/drafts",
        headers=headers,
        json={
            "company_name": "Acme",
            "document_id": str(doc.id),
            "recipient_email": "hiring-manager@acme.example.com",
        },
    )
    data = assert_success(response)
    assert "rq_job_id" in data


def test_outreach_list_route_returns_envelope(client: TestClient) -> None:
    headers = _auth_headers()
    response = client.get("/api/outreach", headers=headers)
    data = assert_success(response)
    assert "messages" in data


async def test_outreach_edit_route(
    client: TestClient, completed_document: dict[str, Any], db: AsyncSession
) -> None:
    from app.modules.outreach.models import OutreachMessage

    user_id = completed_document["user_id"]
    message = OutreachMessage(
        id=uuid4(),
        user_id=user_id,
        company_name="Acme",
        subject="Original subject",
        body="Original body",
        status="draft",
    )
    db.add(message)
    await db.commit()

    headers = _auth_headers(str(user_id))
    response = client.patch(
        f"/api/outreach/{message.id}",
        headers=headers,
        json={"subject": "New subject", "body": "New body"},
    )
    data = assert_success(response)
    assert data["subject"] == "New subject"


async def test_outreach_send_route(
    client: TestClient, completed_document: dict[str, Any], db: AsyncSession
) -> None:
    from app.modules.outreach.models import OutreachMessage

    user_id = completed_document["user_id"]
    message = OutreachMessage(
        id=uuid4(),
        user_id=user_id,
        company_name="Acme",
        subject="Subject",
        body="Body",
        status="draft",
        recipient_email="hiring-manager@acme.example.com",
    )
    db.add(message)
    await db.commit()

    headers = _auth_headers(str(user_id))
    response = client.post(f"/api/outreach/{message.id}/send", headers=headers)
    data = assert_success(response)
    assert data["status"] == "sent"
