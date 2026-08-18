"""Tests for the outreach draft-generation RQ worker task (app/workers/tasks/outreach.py).

Follows the same SessionLocal-context-manager mocking convention used by
tests/test_error_tracking.py's `test_worker_path_captures_and_reraises`.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.domain.candidate import CVData
from app.modules.documents.models import CandidateDocument
from app.modules.outreach.models import OutreachMessage
from app.workers.tasks.outreach import (
    _draft_with_llm,
    _generate_outreach_draft_job,
    generate_outreach_draft_job,
)


class _SessionCM:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


def _patched_worker_session(db: AsyncSession) -> Any:
    return patch(
        "app.workers.tasks.outreach.SessionLocal",
        side_effect=lambda: _SessionCM(db),
    )


@pytest.fixture
async def worker_user(db: AsyncSession) -> User:
    user = User(
        id=uuid4(),
        email=f"outreach-worker-{uuid4().hex[:8]}@example.com",
        first_name="Worker",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def worker_document(db: AsyncSession, worker_user: User) -> CandidateDocument:
    doc = CandidateDocument(
        id=uuid4(),
        user_id=worker_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"outreach-worker-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        extracted_data={"current_role": "Backend Engineer", "technical_skills": ["python", "go"]},
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def test_generate_outreach_draft_job_success(
    db: AsyncSession, worker_user: User, worker_document: CandidateDocument
) -> None:
    with (
        _patched_worker_session(db),
        patch("app.workers.tasks.outreach.close_redis", new=AsyncMock()),
        patch("app.workers.tasks.outreach.engine") as mock_engine,
        patch(
            "app.workers.tasks.outreach.PerplexityClient.get_company_context",
            new=AsyncMock(
                return_value={
                    "summary": "Acme builds widgets",
                    "source": "perplexity",
                    "citations": [],
                }
            ),
        ),
        patch(
            "app.workers.tasks.outreach._draft_with_llm",
            new=AsyncMock(return_value=("Interested in Acme", "Hello, I would love to join Acme.")),
        ),
    ):
        mock_engine.dispose = AsyncMock()
        await _generate_outreach_draft_job(
            str(worker_user.id), str(worker_document.id), "Acme", "Engineer", None
        )

    result = await db.execute(
        select(OutreachMessage).where(OutreachMessage.user_id == worker_user.id)
    )
    message = result.scalar_one()
    assert message.company_name == "Acme"
    assert message.subject == "Interested in Acme"
    assert message.status == "draft"
    assert message.company_context_used == {
        "summary": "Acme builds widgets",
        "source": "perplexity",
        "citations": [],
    }


async def test_generate_outreach_draft_job_missing_document_raises(
    db: AsyncSession, worker_user: User
) -> None:
    with (
        _patched_worker_session(db),
        patch("app.workers.tasks.outreach.close_redis", new=AsyncMock()),
        patch("app.workers.tasks.outreach.engine") as mock_engine,
    ):
        mock_engine.dispose = AsyncMock()
        with pytest.raises(ValueError, match="not found"):
            await _generate_outreach_draft_job(
                str(worker_user.id), str(uuid4()), "Acme", None, None
            )


def test_generate_outreach_draft_job_sync_wrapper_invokes_async_impl() -> None:
    with patch(
        "app.workers.tasks.outreach._generate_outreach_draft_job", new=AsyncMock()
    ) as mock_async_impl:
        generate_outreach_draft_job("user-1", "doc-1", "Acme", "Engineer", "match-1")
    mock_async_impl.assert_called_once_with("user-1", "doc-1", "Acme", "Engineer", "match-1")


async def test_draft_with_llm_returns_generic_message_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    subject, body = await _draft_with_llm(cv_data, "Acme", "Backend Engineer", "", None, settings)

    assert "Acme" in subject
    assert "Backend Engineer" in body


async def test_draft_with_llm_calls_openai_and_parses_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(
        current_role="Engineer", technical_skills=["python", "go"], total_years_experience=5.0
    )

    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: {
        "choices": [{"message": {"content": '{"subject": "Hi Acme", "body": "Custom body"}'}}]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        subject, body = await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "Acme context",
            "We need a Python expert.",
            settings,
        )

    assert subject == "Hi Acme"
    assert body == "Custom body"
    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    assert "We need a Python expert." in user_message


async def test_draft_with_llm_retries_transient_error_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First OpenAI call's raise_for_status() raises a transient 503; with_transient_retry
    should retry and succeed on the second attempt without _draft_with_llm itself raising —
    proving raise_for_status() runs inside the retried closure, so HTTP status errors (not
    just network exceptions) trigger a retry."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(
        current_role="Engineer", technical_skills=["python", "go"], total_years_experience=5.0
    )

    failing_response = AsyncMock()
    failing_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Service Unavailable", request=MagicMock(), response=MagicMock(status_code=503)
        )
    )

    success_response = AsyncMock()
    success_response.raise_for_status = lambda: None
    success_response.json = lambda: {
        "choices": [{"message": {"content": '{"subject": "Hi Acme", "body": "Custom body"}'}}]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=[failing_response, success_response])
    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm),
        patch("app.clients.retry.asyncio.sleep", new=AsyncMock()),
    ):
        subject, body = await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "Acme context",
            "We need a Python expert.",
            settings,
        )

    assert mock_client.post.call_count == 2
    assert subject == "Hi Acme"
    assert body == "Custom body"


async def test_get_job_description_returns_none_without_job_match_id(db: AsyncSession) -> None:
    from app.workers.tasks.outreach import _get_job_description

    result = await _get_job_description(db, None, uuid4())
    assert result is None


async def test_generate_outreach_draft_job_includes_job_description_from_match(
    db: AsyncSession, worker_user: User, worker_document: CandidateDocument
) -> None:
    """Feature-5 spec requires drafts to pull context from the job description — this
    verifies the worker actually looks up the matched posting's description_raw and
    threads it into _draft_with_llm, instead of only ever passing None."""
    from app.modules.job_matching.models import JobMatch, JobPosting

    posting = JobPosting(
        id=uuid4(),
        dedup_key=f"dedup-{uuid4().hex}",
        title="Backend Engineer",
        company="Acme",
        source="test",
        description_raw="We are looking for a backend engineer with Python and Redis experience.",
    )
    db.add(posting)
    await db.flush()

    match = JobMatch(
        id=uuid4(),
        user_id=worker_user.id,
        job_posting_id=posting.id,
        similarity_score=0.8,
        rule_score=0.8,
        overall_score=80.0,
    )
    db.add(match)
    await db.commit()

    captured_kwargs: dict[str, Any] = {}

    async def _fake_draft_with_llm(
        cv_data, company_name, role_title, company_context, job_description, settings
    ):
        captured_kwargs["job_description"] = job_description
        return "Interested in Acme", "Hello, I would love to join Acme."

    with (
        _patched_worker_session(db),
        patch("app.workers.tasks.outreach.close_redis", new=AsyncMock()),
        patch("app.workers.tasks.outreach.engine") as mock_engine,
        patch(
            "app.workers.tasks.outreach.PerplexityClient.get_company_context",
            new=AsyncMock(return_value={"summary": "", "source": "none"}),
        ),
        patch("app.workers.tasks.outreach._draft_with_llm", new=_fake_draft_with_llm),
    ):
        mock_engine.dispose = AsyncMock()
        await _generate_outreach_draft_job(
            str(worker_user.id), str(worker_document.id), "Acme", "Engineer", str(match.id)
        )

    assert captured_kwargs["job_description"] == (
        "We are looking for a backend engineer with Python and Redis experience."
    )
