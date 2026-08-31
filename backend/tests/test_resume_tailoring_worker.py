"""Tests for the resume-tailoring RQ worker task
(app/workers/tasks/resume_tailoring.py). Perplexity + OpenAI mocked. Follows
the same SessionLocal-context-manager mocking convention as
tests/test_outreach_worker.py.
"""

from __future__ import annotations

import json
import sys
import types
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
from app.modules.admin.ai_supervision_models import AiActionAuditLog
from app.modules.documents.models import CandidateDocument
from app.workers.tasks.resume_tailoring import (
    _demand_context_line_for_tailoring,
    _tailor_resume_job,
    _tailor_with_llm,
    tailor_resume_job,
)


def _install_fake_demand_intelligence_service(
    monkeypatch: pytest.MonkeyPatch, mock_fn: Any
) -> None:
    """Install (or override) `app.modules.demand_intelligence.service` with a
    fake module exposing `get_top_countries_for_role=mock_fn`.

    Track 10 was built in parallel with track 02 (which owns
    `app.modules.demand_intelligence`) in the same working tree, so that real
    module/submodule may or may not exist yet at test-collection time
    depending on dispatch/merge order. Patching via `sys.modules` (reverted
    automatically by `monkeypatch` after the test) works whether the real
    module is present or not, unlike `unittest.mock.patch("...:string target",
    create=True)`, which still requires the target *module* to already be
    importable.
    """
    import app.modules.demand_intelligence as real_pkg

    fake_service = types.ModuleType("app.modules.demand_intelligence.service")
    fake_service.get_top_countries_for_role = mock_fn
    monkeypatch.setitem(sys.modules, "app.modules.demand_intelligence.service", fake_service)
    monkeypatch.setattr(real_pkg, "service", fake_service, raising=False)


class _SessionCM:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


def _patched_worker_session(db: AsyncSession) -> Any:
    return patch(
        "app.workers.tasks.resume_tailoring.SessionLocal",
        side_effect=lambda: _SessionCM(db),
    )


@pytest.fixture
async def worker_user(db: AsyncSession) -> User:
    user = User(
        id=uuid4(),
        email=f"resume-tailoring-worker-{uuid4().hex[:8]}@example.com",
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
        file_hash=f"resume-tailoring-worker-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        extracted_data={"current_role": "Backend Engineer", "technical_skills": ["python", "go"]},
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


def _mock_openai_client(content: str):
    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: {"choices": [{"message": {"content": content}}]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_client, mock_client_cm


async def test_tailor_resume_job_success(
    db: AsyncSession, worker_user: User, worker_document: CandidateDocument
) -> None:
    with (
        _patched_worker_session(db),
        patch("app.workers.tasks.resume_tailoring.close_redis", new=AsyncMock()),
        patch("app.workers.tasks.resume_tailoring.engine") as mock_engine,
        patch(
            "app.workers.tasks.resume_tailoring.PerplexityClient.get_company_context",
            new=AsyncMock(return_value={"summary": "Acme builds widgets", "source": "perplexity"}),
        ),
        patch(
            "app.workers.tasks.resume_tailoring._tailor_with_llm",
            new=AsyncMock(
                return_value={
                    "summary": "Tailored summary",
                    "emphasized_skills": ["python"],
                    "reordered_bullets": ["Did a thing"],
                }
            ),
        ),
    ):
        mock_engine.dispose = AsyncMock()
        result = await _tailor_resume_job(
            str(worker_user.id), str(worker_document.id), "Acme", "Backend Engineer"
        )

    assert result["summary"] == "Tailored summary"
    assert result["research_degraded"] is False


async def test_tailor_resume_job_marks_research_degraded_when_perplexity_unavailable(
    db: AsyncSession, worker_user: User, worker_document: CandidateDocument
) -> None:
    with (
        _patched_worker_session(db),
        patch("app.workers.tasks.resume_tailoring.close_redis", new=AsyncMock()),
        patch("app.workers.tasks.resume_tailoring.engine") as mock_engine,
        patch(
            "app.workers.tasks.resume_tailoring.PerplexityClient.get_company_context",
            new=AsyncMock(return_value={"summary": "", "source": "none"}),
        ),
        patch(
            "app.workers.tasks.resume_tailoring._tailor_with_llm",
            new=AsyncMock(
                return_value={
                    "summary": "Tailored summary",
                    "emphasized_skills": [],
                    "reordered_bullets": [],
                }
            ),
        ),
    ):
        mock_engine.dispose = AsyncMock()
        result = await _tailor_resume_job(str(worker_user.id), str(worker_document.id), "Acme")

    assert result["research_degraded"] is True


async def test_tailor_resume_job_records_ai_action_audit_row_without_persisting_content(
    db: AsyncSession, worker_user: User, worker_document: CandidateDocument
) -> None:
    """After the tailored result is generated, record_ai_action() must be
    called with action_type='resume_tailoring' -- and, per the release-blocking
    ephemeral-only invariant for this track, the audit row's summary must be
    a short descriptive string, never the tailored resume content itself
    (verified by asserting the actual tailored summary text is absent from
    the persisted audit row's summary column)."""
    with (
        _patched_worker_session(db),
        patch("app.workers.tasks.resume_tailoring.close_redis", new=AsyncMock()),
        patch("app.workers.tasks.resume_tailoring.engine") as mock_engine,
        patch(
            "app.workers.tasks.resume_tailoring.PerplexityClient.get_company_context",
            new=AsyncMock(return_value={"summary": "Acme builds widgets", "source": "perplexity"}),
        ),
        patch(
            "app.workers.tasks.resume_tailoring._tailor_with_llm",
            new=AsyncMock(
                return_value={
                    "summary": "This is the full tailored resume summary text.",
                    "emphasized_skills": ["python"],
                    "reordered_bullets": ["Did a thing"],
                }
            ),
        ),
    ):
        mock_engine.dispose = AsyncMock()
        await _tailor_resume_job(
            str(worker_user.id), str(worker_document.id), "Acme", "Backend Engineer"
        )

    result = await db.execute(
        select(AiActionAuditLog).where(AiActionAuditLog.candidate_user_id == worker_user.id)
    )
    audit_row = result.scalar_one()
    assert audit_row.action_type == "resume_tailoring"
    assert audit_row.related_id is None
    assert audit_row.summary == "target_company=Acme, target_role=Backend Engineer"
    assert "This is the full tailored resume summary text." not in audit_row.summary


async def test_tailor_resume_job_missing_document_raises(
    db: AsyncSession, worker_user: User
) -> None:
    with (
        _patched_worker_session(db),
        patch("app.workers.tasks.resume_tailoring.close_redis", new=AsyncMock()),
        patch("app.workers.tasks.resume_tailoring.engine") as mock_engine,
    ):
        mock_engine.dispose = AsyncMock()
        with pytest.raises(ValueError, match="not found"):
            await _tailor_resume_job(str(worker_user.id), str(uuid4()), "Acme")


async def test_tailor_resume_job_document_not_owned_by_caller_raises(
    db: AsyncSession, worker_document: CandidateDocument
) -> None:
    """Document exists but belongs to a different user — must not leak another
    candidate's tailored resume."""
    with (
        _patched_worker_session(db),
        patch("app.workers.tasks.resume_tailoring.close_redis", new=AsyncMock()),
        patch("app.workers.tasks.resume_tailoring.engine") as mock_engine,
    ):
        mock_engine.dispose = AsyncMock()
        with pytest.raises(ValueError, match="not found"):
            await _tailor_resume_job(str(uuid4()), str(worker_document.id), "Acme")


def test_tailor_resume_job_sync_wrapper_invokes_async_impl() -> None:
    with patch(
        "app.workers.tasks.resume_tailoring._tailor_resume_job", new=AsyncMock()
    ) as mock_async_impl:
        tailor_resume_job("user-1", "doc-1", "Acme", "Backend Engineer")
    mock_async_impl.assert_called_once_with("user-1", "doc-1", "Acme", "Backend Engineer")


async def test_tailor_with_llm_returns_offline_fallback_without_api_key(
    monkeypatch: pytest.MonkeyPatch, db: AsyncSession
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    result = await _tailor_with_llm(cv_data, "Acme", "Backend Engineer", "", settings, db)

    assert "Acme" in result["summary"]
    assert result["emphasized_skills"] == ["python"]
    assert result["reordered_bullets"] == []


async def test_tailor_with_llm_calls_openai_and_parses_response(
    monkeypatch: pytest.MonkeyPatch, db: AsyncSession
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(
        current_role="Engineer", technical_skills=["python", "go"], total_years_experience=5.0
    )

    fake_content = json.dumps(
        {
            "summary": "Tailored summary",
            "emphasized_skills": ["python"],
            "reordered_bullets": ["Did a thing"],
        }
    )
    mock_client, mock_client_cm = _mock_openai_client(fake_content)
    with patch("app.workers.tasks.resume_tailoring.httpx.AsyncClient", return_value=mock_client_cm):
        result = await _tailor_with_llm(
            cv_data, "Acme", "Backend Engineer", "Acme context", settings, db
        )

    assert result["summary"] == "Tailored summary"
    assert result["emphasized_skills"] == ["python"]
    assert result["reordered_bullets"] == ["Did a thing"]
    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    assert "Acme context" in user_message


async def test_tailor_with_llm_retries_transient_error_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, db: AsyncSession
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    failing_response = AsyncMock()
    failing_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Service Unavailable", request=MagicMock(), response=MagicMock(status_code=503)
        )
    )
    success_response = AsyncMock()
    success_response.raise_for_status = lambda: None
    success_response.json = lambda: {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "summary": "Tailored summary",
                            "emphasized_skills": [],
                            "reordered_bullets": [],
                        }
                    )
                }
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=[failing_response, success_response])
    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.workers.tasks.resume_tailoring.httpx.AsyncClient", return_value=mock_client_cm),
        patch("app.clients.retry.asyncio.sleep", new=AsyncMock()),
    ):
        result = await _tailor_with_llm(cv_data, "Acme", "Backend Engineer", "", settings, db)

    assert mock_client.post.call_count == 2
    assert result["summary"] == "Tailored summary"


async def test_demand_context_line_flag_off_returns_none_without_query(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zero extra DB round-trips when the flag is off — mirrors 07's identical
    requirement."""
    settings = get_settings()
    settings.enable_demand_intelligence_in_resume_tailoring = False
    cv_data = CVData(desired_roles=["Backend Engineer"])

    mock_get_top_countries = AsyncMock()
    _install_fake_demand_intelligence_service(monkeypatch, mock_get_top_countries)

    result = await _demand_context_line_for_tailoring(cv_data, None, settings, db)

    assert result is None
    mock_get_top_countries.assert_not_called()


async def test_demand_context_line_flag_on_no_role_signal_returns_none(db: AsyncSession) -> None:
    settings = get_settings()
    settings.enable_demand_intelligence_in_resume_tailoring = True
    cv_data = CVData(desired_roles=[])

    result = await _demand_context_line_for_tailoring(cv_data, None, settings, db)

    assert result is None


async def test_demand_context_line_flag_on_uses_target_role_first(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    settings.enable_demand_intelligence_in_resume_tailoring = True
    cv_data = CVData(desired_roles=["Fallback Role"])

    fake_snapshot_in = MagicMock(country_iso2="in")
    fake_snapshot_ae = MagicMock(country_iso2="ae")

    mock_get_top_countries = AsyncMock(return_value=[fake_snapshot_in, fake_snapshot_ae])
    _install_fake_demand_intelligence_service(monkeypatch, mock_get_top_countries)

    result = await _demand_context_line_for_tailoring(cv_data, "Backend Engineer", settings, db)

    assert result is not None
    assert "IN, AE" in result
    assert "Backend Engineer" in result
    mock_get_top_countries.assert_called_once_with(db, "Backend Engineer", limit=3)


async def test_demand_context_line_flag_on_no_snapshot_match_returns_none(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    settings.enable_demand_intelligence_in_resume_tailoring = True
    cv_data = CVData(desired_roles=["Backend Engineer"])

    _install_fake_demand_intelligence_service(monkeypatch, AsyncMock(return_value=[]))

    result = await _demand_context_line_for_tailoring(cv_data, None, settings, db)

    assert result is None


async def test_tailor_with_llm_user_content_byte_identical_when_flag_off(
    monkeypatch: pytest.MonkeyPatch, db: AsyncSession
) -> None:
    """Regression (required, byte-identical check): with the flag off (the
    default), the constructed user_content must be identical to what it
    would have been before the demand-intelligence injection section
    existed — no stray demand line appended."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    settings.enable_demand_intelligence_in_resume_tailoring = False
    cv_data = CVData(
        current_role="Engineer",
        technical_skills=["python", "go"],
        total_years_experience=5.0,
        desired_roles=["Backend Engineer"],
    )

    fake_content = json.dumps({"summary": "s", "emphasized_skills": [], "reordered_bullets": []})
    mock_client, mock_client_cm = _mock_openai_client(fake_content)
    with patch("app.workers.tasks.resume_tailoring.httpx.AsyncClient", return_value=mock_client_cm):
        await _tailor_with_llm(cv_data, "Acme", "Backend Engineer", "Acme context", settings, db)

    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")

    expected_user_content = (
        "Candidate background: Current role: Engineer. Skills: python, go. "
        "Years of experience: 5.0. Work history: [].\n"
        "Target company: Acme\n"
        "Target role: Backend Engineer\n"
        "Public company context: Acme context"
    )
    assert user_message == expected_user_content
    assert "Note:" not in user_message


async def test_tailor_with_llm_includes_demand_line_when_flag_on_and_snapshot_matches(
    monkeypatch: pytest.MonkeyPatch, db: AsyncSession
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    settings.enable_demand_intelligence_in_resume_tailoring = True
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    fake_snapshot = MagicMock(country_iso2="in")
    fake_content = json.dumps({"summary": "s", "emphasized_skills": [], "reordered_bullets": []})
    mock_client, mock_client_cm = _mock_openai_client(fake_content)
    _install_fake_demand_intelligence_service(monkeypatch, AsyncMock(return_value=[fake_snapshot]))
    with patch("app.workers.tasks.resume_tailoring.httpx.AsyncClient", return_value=mock_client_cm):
        await _tailor_with_llm(cv_data, "Acme", "Backend Engineer", "Acme context", settings, db)

    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    assert "Note: recent job-market data" in user_message
    assert "IN" in user_message
