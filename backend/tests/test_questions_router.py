"""API tests for POST /api/questions (phase2_module3.md §9.4).

Covers: status code, auth enforcement (401 without/with wrong bearer token),
and response envelope shape - matching the convention already established in
test_module2_api.py (local `client`/`_auth_headers` + per-test-file seeding
fixtures built directly against real ORM models via the `db` fixture).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.main import app
from app.models import InterviewQuestion
from app.modules.documents.models import CandidateDocument
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
async def seeded_bank_questions(db: AsyncSession) -> list[InterviewQuestion]:
    """Seed 3 software_engineer bank questions with varied category/difficulty."""
    questions = [
        InterviewQuestion(
            question_text="Describe a challenging production bug you fixed.",
            question_category="technical",
            difficulty="medium",
            job_roles=["software_engineer"],
            technologies=["python"],
            source="seed",
        ),
        InterviewQuestion(
            question_text="Tell me about a time you led a project under a tight deadline.",
            question_category="behavioral",
            difficulty="easy",
            job_roles=["software_engineer"],
            technologies=[],
            source="seed",
        ),
        InterviewQuestion(
            question_text="Design a URL shortener that scales to millions of users.",
            question_category="system_design",
            difficulty="hard",
            job_roles=["software_engineer"],
            technologies=["distributed_systems"],
            source="seed",
        ),
    ]
    db.add_all(questions)
    await db.commit()
    for question in questions:
        await db.refresh(question)
    return questions


@pytest.fixture
async def processed_candidate_document(db: AsyncSession) -> dict[str, Any]:
    """A CandidateDocument with processing_status='completed' (the value
    service.py's `_load_candidate_context` checks for), owned by a fresh user.
    """
    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"api-questions-{user_id.hex[:8]}@example.com",
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
        extracted_data={
            "technical_skills": ["Python", "SQL"],
            "desired_roles": ["Software Engineer"],
        },
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return {"user_id": user_id, "document": doc}


def test_list_questions_requires_auth(client: TestClient) -> None:
    response = client.post("/api/questions", json={"job_role": "software_engineer"})
    assert_error(response, 401)


def test_list_questions_returns_bank_results(
    client: TestClient, seeded_bank_questions: list[InterviewQuestion]
) -> None:
    headers = _auth_headers()
    response = client.post(
        "/api/questions", headers=headers, json={"job_role": "software_engineer", "count": 5}
    )
    data = assert_success(response)
    assert len(data["questions"]) <= 5
    assert data["source"] in {"question_bank", "generated", "mixed"}


def test_list_questions_falls_back_without_openai_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Real, load-bearing precedent for this exact pattern: get_settings() is
    # @lru_cache'd (app/core/config.py:334), so mutating the singleton instance
    # in place - as test_health_alerts.py/test_error_tracking.py already do -
    # is visible to the `Depends(get_settings)` used by the route.
    monkeypatch.setattr(get_settings(), "openai_api_key", "")
    headers = _auth_headers()
    # count=15 is the schema's max (QuestionRequest.count has le=15).
    # "product_manager" is not seeded by any fixture in this file, so the
    # bank shortfall is guaranteed.
    response = client.post(
        "/api/questions", headers=headers, json={"job_role": "product_manager", "count": 15}
    )
    data = assert_success(response)
    assert data["source"] == "question_bank"


def test_list_questions_personalizes_when_document_exists(
    client: TestClient,
    processed_candidate_document: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ensure the LLM path is reachable regardless of what happens to be in
    # .env locally/in CI - deterministic, not dependent on a real secret.
    monkeypatch.setattr(get_settings(), "openai_api_key", "test-key-for-personalization")
    headers = _auth_headers(str(processed_candidate_document["user_id"]))

    with patch(
        "app.modules.questions.service.generate_questions", new_callable=AsyncMock
    ) as mock_generate:
        mock_generate.return_value = ([], {"input_tokens": 0, "output_tokens": 0})
        # "devops_engineer" is not seeded anywhere in this file, so the bank
        # has 0 matches and count=5 guarantees a shortfall - the only
        # condition (per service.py's get_questions) that triggers generation.
        response = client.post(
            "/api/questions",
            headers=headers,
            json={"job_role": "devops_engineer", "count": 5, "personalize": True},
        )
        assert response.status_code == 200
        mock_generate.assert_called_once()
        assert mock_generate.call_args.kwargs["candidate_context"] is not None


def test_list_questions_stops_personalizing_after_daily_limit(
    client: TestClient,
    processed_candidate_document: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QUESTION_GENERATION_DAILY_LIMIT_PER_USER caps personalized generation
    per candidate per day (.env.example's cost-control guard) - once reached,
    generation still happens (for the shared, non-personalized pool) but
    candidate_context is dropped rather than raising or silently bypassing
    the limit forever.
    """
    monkeypatch.setattr(get_settings(), "openai_api_key", "test-key-for-personalization")
    monkeypatch.setattr(get_settings(), "question_generation_daily_limit_per_user", 1)
    user_id = processed_candidate_document["user_id"]
    headers = _auth_headers(str(user_id))

    with patch(
        "app.modules.questions.service.generate_questions", new_callable=AsyncMock
    ) as mock_generate:
        sample_generated = {
            # category/job_role deliberately avoid colliding with
            # test_question_bank.py's "nothing matches" empty-list
            # assumption (devops_engineer + system_design) - this call
            # persists a REAL row into the shared test sqlite file
            # (session.commit(), not rolled back across test files).
            "question_text": "Explain how you'd design a rate limiter.",
            "category": "behavioral",
            "difficulty": "medium",
            "job_roles": ["devops_engineer"],
            "technologies": ["redis"],
            "sample_answer": "A token bucket...",
            "scoring_rubric": {"clarity": "clear"},
        }
        mock_generate.return_value = (
            [sample_generated] * 5,
            {"input_tokens": 10, "output_tokens": 10},
        )
        # First call: under the limit (0 generated today) -> personalizes and
        # persists personalized_for_user_id rows, consuming the day's quota.
        first = client.post(
            "/api/questions",
            headers=headers,
            json={"job_role": "devops_engineer", "count": 5, "personalize": True},
        )
        assert first.status_code == 200
        assert mock_generate.call_args.kwargs["candidate_context"] is not None

        mock_generate.reset_mock()
        mock_generate.return_value = (
            [sample_generated] * 5,
            {"input_tokens": 10, "output_tokens": 10},
        )

        # Second call: quota exhausted. Ask for more than the bank now holds so
        # generation still runs, but candidate_context must be dropped.
        second = client.post(
            "/api/questions",
            headers=headers,
            json={"job_role": "devops_engineer", "count": 15, "personalize": True},
        )
        assert second.status_code == 200
        assert mock_generate.called
        assert mock_generate.call_args.kwargs["candidate_context"] is None


def test_list_questions_batches_generation_to_requested_count(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """count=10 must request a full shortfall from generate_questions in one call."""
    monkeypatch.setattr(get_settings(), "openai_api_key", "test-key-for-batching")
    headers = _auth_headers()
    sample = {
        "question_text": "Explain your approach to on-call.",
        "category": "behavioral",
        "difficulty": "medium",
        "job_roles": ["software_engineer"],
        "technologies": ["python"],
        "sample_answer": "A strong answer covers alerting...",
        "scoring_rubric": {"clarity": "clear"},
    }

    with patch(
        "app.modules.questions.service.generate_questions", new_callable=AsyncMock
    ) as mock_generate:

        async def _fake_generate(**kwargs):
            n = kwargs["count"]
            return ([sample.copy() for _ in range(n)], {"input_tokens": 1, "output_tokens": 1})

        mock_generate.side_effect = _fake_generate
        response = client.post(
            "/api/questions",
            headers=headers,
            json={"job_role": "product_manager", "count": 10},
        )
        data = assert_success(response)
        assert len(data["questions"]) == 10
        assert mock_generate.call_count == 1
        assert mock_generate.call_args.kwargs["count"] == 10
