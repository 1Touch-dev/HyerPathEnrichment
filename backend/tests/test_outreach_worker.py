"""Tests for the outreach draft-generation RQ worker task (app/workers/tasks/outreach.py).

Follows the same SessionLocal-context-manager mocking convention used by
tests/test_error_tracking.py's `test_worker_path_captures_and_reraises`.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.database.session import SessionLocal
from app.domain.candidate import CVData
from app.modules.admin.ai_supervision_models import AiActionAuditLog
from app.modules.documents.models import CandidateDocument
from app.modules.outreach.models import EmployerCompanyTier, OutreachMessage
from app.workers.tasks.outreach import (
    _COMPANY_TIER_INSTRUCTIONS,
    _COMPANY_TIER_JSON_SCHEMA,
    _CUSTOM_INSTRUCTION_PREFIX,
    _EMAIL_SYSTEM_PROMPT,
    _GENERIC_SYSTEM_PROMPT,
    _LINKEDIN_SYSTEM_PROMPT,
    _ROLE_TYPE_INSTRUCTIONS,
    _STRATEGY_INSTRUCTIONS,
    _draft_with_llm,
    _generate_outreach_draft_job,
    classify_company_tier,
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


async def test_generate_outreach_draft_job_calls_flag_if_needed(
    db: AsyncSession, worker_user: User, worker_document: CandidateDocument
) -> None:
    """`flag_if_needed` must be called after the `OutreachMessage` row is
    committed, with the message's own resource_type/resource_id/text_fields.
    `flag_if_needed`'s own internals are covered by
    `test_admin_moderation_flagging.py` — this only asserts call-site wiring.
    """
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
        patch("app.workers.tasks.outreach.flag_if_needed", new_callable=AsyncMock) as mock_flag,
    ):
        mock_engine.dispose = AsyncMock()
        await _generate_outreach_draft_job(
            str(worker_user.id), str(worker_document.id), "Acme", "Engineer", None
        )

    result = await db.execute(
        select(OutreachMessage).where(OutreachMessage.user_id == worker_user.id)
    )
    message = result.scalar_one()

    mock_flag.assert_called_once()
    _, kwargs = mock_flag.call_args
    assert kwargs["resource_type"] == "outreach_message"
    assert kwargs["resource_id"] == message.id
    assert kwargs["text_fields"] == ["Interested in Acme", "Hello, I would love to join Acme."]


async def test_generate_outreach_draft_job_flag_if_needed_failure_does_not_break_draft(
    db: AsyncSession, worker_user: User, worker_document: CandidateDocument
) -> None:
    """The most important guarantee this chunk is responsible for: if
    `flag_if_needed` raises an unexpected exception, draft generation must
    still complete successfully and persist the `OutreachMessage` row."""
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
        patch(
            "app.workers.tasks.outreach.flag_if_needed",
            new_callable=AsyncMock,
            side_effect=RuntimeError("simulated flagging bug"),
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
    assert message.status == "draft"
    assert message.subject == "Interested in Acme"


async def test_generate_outreach_draft_job_records_ai_action_audit_row(
    db: AsyncSession, worker_user: User, worker_document: CandidateDocument
) -> None:
    """After the OutreachMessage is committed, record_ai_action() must be
    called with action_type='outreach_draft' and related_id=message.id --
    verified here by querying the ai_action_audit_log table for the row it
    should have written (mirrors this file's existing db-query convention)."""
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

    message_result = await db.execute(
        select(OutreachMessage).where(OutreachMessage.user_id == worker_user.id)
    )
    message = message_result.scalar_one()

    audit_result = await db.execute(
        select(AiActionAuditLog).where(AiActionAuditLog.related_id == message.id)
    )
    audit_row = audit_result.scalar_one()
    assert audit_row.action_type == "outreach_draft"
    assert audit_row.candidate_user_id == worker_user.id
    assert audit_row.summary is not None


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
    mock_async_impl.assert_called_once_with(
        "user-1",
        "doc-1",
        "Acme",
        "Engineer",
        "match-1",
        "email",
        None,
        None,
        "direct_pitch",
        None,
        None,
        None,
        None,
        None,
    )


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


async def test_get_job_description_returns_none_for_manual_entry_match_with_no_crash(
    db: AsyncSession, worker_user: User
) -> None:
    """Regression test (Module F, §10.6): a JobMatch for a manually-added job
    (job_posting_id NULL, manual_job_entry_id set) has no JobPosting row to look up a
    description from. Before this fix, this hit an unconditional `select(JobPosting)
    .where(JobPosting.id == match.job_posting_id)` — this asserts the early-return
    guard added for `job_posting_id is None` returns cleanly, not just that the
    (already-defensive) `if not posting` check downstream happens to save it.
    """
    from app.modules.job_matching.models import JobMatch
    from app.modules.manual_jobs.models import ManualJobEntry
    from app.workers.tasks.outreach import _get_job_description

    entry = ManualJobEntry(
        id=uuid4(),
        user_id=worker_user.id,
        title="Self-Sourced Role",
        company="Referral Co",
    )
    db.add(entry)
    await db.flush()

    match = JobMatch(
        id=uuid4(),
        user_id=worker_user.id,
        job_posting_id=None,
        manual_job_entry_id=entry.id,
        similarity_score=0.0,
        rule_score=0.0,
        overall_score=0.0,
        score_breakdown={},
        application_status="new",
    )
    db.add(match)
    await db.commit()

    result = await _get_job_description(db, str(match.id), worker_user.id)
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
        cv_data,
        company_name,
        role_title,
        company_context,
        job_description,
        settings,
        message_type="email",
        custom_instruction=None,
        strategy="direct_pitch",
        referral_context=None,
        role_type=None,
        seniority=None,
        company_tier=None,
        db=None,
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


async def test_generate_outreach_draft_job_prefers_pasted_job_description(
    db: AsyncSession, worker_user: User, worker_document: CandidateDocument
) -> None:
    """Pasted JD text must win over JobPosting.description_raw when both are present."""
    from app.modules.job_matching.models import JobMatch, JobPosting

    posting = JobPosting(
        id=uuid4(),
        dedup_key=f"dedup-{uuid4().hex}",
        title="Backend Engineer",
        company="Acme",
        source="test",
        description_raw="Matched posting description that should be ignored.",
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

    pasted = "Pasted JD: looking for a platform engineer with Kubernetes and Go experience."
    captured_kwargs: dict[str, Any] = {}

    async def _fake_draft_with_llm(
        cv_data,
        company_name,
        role_title,
        company_context,
        job_description,
        settings,
        message_type="email",
        custom_instruction=None,
        strategy="direct_pitch",
        referral_context=None,
        role_type=None,
        seniority=None,
        company_tier=None,
        db=None,
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
            str(worker_user.id),
            str(worker_document.id),
            "Acme",
            "Engineer",
            str(match.id),
            "email",
            None,
            pasted,
        )

    assert captured_kwargs["job_description"] == pasted


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


@pytest.mark.parametrize(
    "message_type,expected_prompt",
    [
        ("email", _EMAIL_SYSTEM_PROMPT),
        ("linkedin", _LINKEDIN_SYSTEM_PROMPT),
        ("generic", _GENERIC_SYSTEM_PROMPT),
        ("custom", _EMAIL_SYSTEM_PROMPT),
    ],
)
async def test_draft_with_llm_selects_system_prompt_per_message_type(
    monkeypatch: pytest.MonkeyPatch, message_type: str, expected_prompt: str
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "Acme context",
            "We need a Python expert.",
            settings,
            message_type,
            "Mention I'm relocating" if message_type == "custom" else None,
        )

    sent_payload = mock_client.post.call_args.kwargs["json"]
    system_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "system")
    assert system_message == expected_prompt


async def test_draft_with_llm_truncates_oversized_linkedin_subject_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    oversized_subject = "S" * (settings.outreach_linkedin_inmail_subject_max_chars + 50)
    oversized_body = "B" * (settings.outreach_linkedin_inmail_body_max_chars + 500)
    fake_content = json.dumps({"subject": oversized_subject, "body": oversized_body})

    _, mock_client_cm = _mock_openai_client(fake_content)
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        subject, body = await _draft_with_llm(
            cv_data, "Acme", "Backend Engineer", "", None, settings, "linkedin", None
        )

    assert len(subject) == settings.outreach_linkedin_inmail_subject_max_chars
    assert subject.endswith("…")
    assert len(body) == settings.outreach_linkedin_inmail_body_max_chars
    assert body.endswith("…")


async def test_draft_with_llm_does_not_truncate_linkedin_within_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    fake_content = json.dumps({"subject": "Short subject", "body": "Short body"})
    _, mock_client_cm = _mock_openai_client(fake_content)
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        subject, body = await _draft_with_llm(
            cv_data, "Acme", "Backend Engineer", "", None, settings, "linkedin", None
        )

    assert subject == "Short subject"
    assert body == "Short body"


async def test_draft_with_llm_custom_mode_includes_instruction_prefix_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    candidate_instruction = "Mention my open-source contributions and keep it upbeat."
    mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "Acme context",
            "We need a Python expert.",
            settings,
            "custom",
            candidate_instruction,
        )

    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    assert _CUSTOM_INSTRUCTION_PREFIX in user_message
    assert candidate_instruction in user_message


# --- machine-2/03: strategy/role-type/company-tier drafting variation ---


@pytest.mark.parametrize("strategy", ["direct_pitch", "value_first", "curiosity", "warm_referral"])
async def test_draft_with_llm_appends_strategy_fragment(
    monkeypatch: pytest.MonkeyPatch, strategy: str
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "Acme context",
            "We need a Python expert.",
            settings,
            "email",
            None,
            strategy,
            "Referred by Jane" if strategy == "warm_referral" else None,
        )

    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    assert _STRATEGY_INSTRUCTIONS[strategy] in user_message


async def test_draft_with_llm_warm_referral_includes_referral_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "",
            None,
            settings,
            "email",
            None,
            "warm_referral",
            "Introduced via Jane Doe, former colleague",
        )

    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    assert "Introduced via Jane Doe, former colleague" in user_message


@pytest.mark.parametrize(
    "role_type,seniority",
    [
        ("technical", "senior"),
        ("technical", "junior"),
        ("non_technical", "senior"),
        ("non_technical", "junior"),
    ],
)
async def test_draft_with_llm_appends_role_type_fragment_when_both_set(
    monkeypatch: pytest.MonkeyPatch, role_type: str, seniority: str
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "",
            None,
            settings,
            "email",
            None,
            "direct_pitch",
            None,
            role_type,
            seniority,
        )

    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    assert _ROLE_TYPE_INSTRUCTIONS[(role_type, seniority)] in user_message


@pytest.mark.parametrize(
    "role_type,seniority", [("technical", None), (None, "senior"), (None, None)]
)
async def test_draft_with_llm_omits_role_type_fragment_for_partial_combination(
    monkeypatch: pytest.MonkeyPatch, role_type: str | None, seniority: str | None
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "",
            None,
            settings,
            "email",
            None,
            "direct_pitch",
            None,
            role_type,
            seniority,
        )

    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    for fragment in _ROLE_TYPE_INSTRUCTIONS.values():
        assert fragment not in user_message


@pytest.mark.parametrize("tier", ["premium", "outsourcing"])
async def test_draft_with_llm_appends_company_tier_fragment_when_tier_set(
    monkeypatch: pytest.MonkeyPatch, tier: str
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "",
            None,
            settings,
            "email",
            None,
            "direct_pitch",
            None,
            None,
            None,
            tier,
        )

    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    assert _COMPANY_TIER_INSTRUCTIONS[tier] in user_message


async def test_draft_with_llm_no_company_tier_fragment_when_tier_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (release-blocking bar): no EmployerCompanyTier row / flag off both
    resolve to `company_tier=None` at the call site, and this must append nothing —
    byte-identical to pre-company-tier-wiring behavior for every other fragment."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    cv_data = CVData(current_role="Engineer", technical_skills=["python"])

    mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "",
            None,
            settings,
            "email",
            None,
            "direct_pitch",
            None,
            None,
            None,
            None,
        )

    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    for fragment in _COMPANY_TIER_INSTRUCTIONS.values():
        assert fragment not in user_message


async def test_generate_outreach_draft_job_skips_company_tier_lookup_when_flag_off(
    db: AsyncSession,
    worker_user: User,
    worker_document: CandidateDocument,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """This repo's chosen resolution (documented in outreach.py) of the
    Verification section's stated ambiguity: gate the get_company_tier() lookup
    itself behind the flag, not just its use in the prompt — zero extra DB calls
    when the flag is off (the default)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_company_tier_in_outreach_drafting", False)

    with (
        _patched_worker_session(db),
        patch("app.workers.tasks.outreach.close_redis", new=AsyncMock()),
        patch("app.workers.tasks.outreach.engine") as mock_engine,
        patch(
            "app.workers.tasks.outreach.PerplexityClient.get_company_context",
            new=AsyncMock(return_value={"summary": "", "source": "none"}),
        ),
        patch(
            "app.workers.tasks.outreach._draft_with_llm",
            new=AsyncMock(return_value=("Interested in Acme", "Body")),
        ),
        patch(
            "app.workers.tasks.outreach.get_company_tier", new=AsyncMock()
        ) as mock_get_company_tier,
    ):
        mock_engine.dispose = AsyncMock()
        await _generate_outreach_draft_job(
            str(worker_user.id), str(worker_document.id), "Acme", "Engineer", None
        )

    mock_get_company_tier.assert_not_called()


async def test_generate_outreach_draft_job_looks_up_company_tier_when_flag_on(
    db: AsyncSession,
    worker_user: User,
    worker_document: CandidateDocument,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.outreach.models import EmployerCompanyTier

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_company_tier_in_outreach_drafting", True)

    company_name = f"Acme-{uuid4().hex[:8]}"
    tier_row = EmployerCompanyTier(company_name=company_name, tier="premium")
    db.add(tier_row)
    await db.commit()

    captured: dict[str, Any] = {}

    async def _fake_draft_with_llm(*args, **kwargs):
        captured["company_tier"] = args[12] if len(args) > 12 else kwargs.get("company_tier")
        return "Interested in Acme", "Body"

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
            str(worker_user.id), str(worker_document.id), company_name, "Engineer", None
        )

    assert captured["company_tier"] == "premium"


# --- machine-2/03: classify_company_tier (structured-output LLM classifier) ---


async def test_classify_company_tier_returns_tier_from_mocked_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")

    _, mock_client_cm = _mock_openai_client('{"tier": "premium"}')
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        result = await classify_company_tier("Acme", "A large well-known tech company.")

    assert result == "premium"


async def test_classify_company_tier_request_uses_strict_json_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release-blocking: the request payload must actually use OpenAI's
    structured-output mode (response_format={"type": "json_schema", ...,
    "strict": True}), not a free-text prompt parsed with json.loads on a
    hope."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")

    mock_client, mock_client_cm = _mock_openai_client('{"tier": "outsourcing"}')
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        await classify_company_tier("Acme", "context")

    sent_payload = mock_client.post.call_args.kwargs["json"]
    assert sent_payload["response_format"] == _COMPANY_TIER_JSON_SCHEMA
    assert sent_payload["response_format"]["json_schema"]["strict"] is True
    assert sent_payload["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert sent_payload["response_format"]["json_schema"]["schema"]["properties"]["tier"][
        "enum"
    ] == ["premium", "outsourcing"]


async def test_classify_company_tier_fails_soft_to_outsourcing_on_http_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never raises: a mocked HTTP/network failure must fail soft to
    'outsourcing', not propagate an exception."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        result = await classify_company_tier("Acme", "context")

    assert result == "outsourcing"


async def test_classify_company_tier_fails_soft_to_outsourcing_on_malformed_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never raises: a schema-invalid/unparseable response (not valid JSON,
    or missing the required 'tier' key) must also fail soft to 'outsourcing',
    not just network errors."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")

    _, mock_client_cm = _mock_openai_client("not valid json at all")
    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        result = await classify_company_tier("Acme", "context")

    assert result == "outsourcing"


async def test_classify_company_tier_fails_soft_to_outsourcing_on_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never raises: a structured-output refusal (surfaced via the "refusal"
    field rather than "content") must also fail soft to 'outsourcing'."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")

    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: {
        "choices": [{"message": {"refusal": "I cannot classify this company."}}]
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm):
        result = await classify_company_tier("Acme", "context")

    assert result == "outsourcing"


async def test_classify_company_tier_returns_outsourcing_when_no_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "")

    result = await classify_company_tier("Acme", "context")

    assert result == "outsourcing"


async def test_generate_outreach_draft_job_classifies_and_persists_when_no_tier_row(
    db: AsyncSession,
    worker_user: User,
    worker_document: CandidateDocument,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the flag is on and no EmployerCompanyTier row exists yet for this
    company, the classifier runs lazily and its result is persisted (set_by=
    'llm', set_by_user_id=None) and used for that same draft."""
    from app.modules.outreach.repository import get_company_tier

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_company_tier_in_outreach_drafting", True)

    company_name = f"NewCo-{uuid4().hex[:8]}"
    captured: dict[str, Any] = {}

    async def _fake_draft_with_llm(*args, **kwargs):
        captured["company_tier"] = args[12] if len(args) > 12 else kwargs.get("company_tier")
        return "Interested in NewCo", "Body"

    with (
        _patched_worker_session(db),
        patch("app.workers.tasks.outreach.close_redis", new=AsyncMock()),
        patch(
            "app.workers.tasks.outreach.get_redis_connection",
            return_value=_RaceLockRedis(),
        ),
        patch("app.workers.tasks.outreach.engine") as mock_engine,
        patch(
            "app.workers.tasks.outreach.PerplexityClient.get_company_context",
            new=AsyncMock(
                return_value={"summary": "A small niche staffing firm.", "source": "perplexity"}
            ),
        ),
        patch("app.workers.tasks.outreach._draft_with_llm", new=_fake_draft_with_llm),
        patch(
            "app.workers.tasks.outreach.classify_company_tier",
            new=AsyncMock(return_value="premium"),
        ) as mock_classify,
    ):
        mock_engine.dispose = AsyncMock()
        await _generate_outreach_draft_job(
            str(worker_user.id), str(worker_document.id), company_name, "Engineer", None
        )

    mock_classify.assert_awaited_once_with(company_name, "A small niche staffing firm.")
    assert captured["company_tier"] == "premium"

    persisted = await get_company_tier(db, company_name)
    assert persisted is not None
    assert persisted.tier == "premium"
    assert persisted.set_by == "llm"
    assert persisted.set_by_user_id is None


# --- machine-2/07: demand-intelligence -> outreach context line ---


def _fake_snapshot(country_iso2: str) -> Any:
    """Minimal stand-in for CountryDemandSnapshot — _demand_context_line only
    ever reads .country_iso2 off each returned row, so a lightweight object
    (rather than a real ORM instance) keeps these tests decoupled from 02's
    module internals."""
    snapshot = MagicMock()
    snapshot.country_iso2 = country_iso2
    return snapshot


async def test_demand_context_line_returns_none_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.workers.tasks.outreach import _demand_context_line

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_demand_intelligence_in_outreach", False)
    cv_data = CVData(desired_roles=["Backend Engineer"])

    with patch(
        "app.workers.tasks.outreach.get_top_countries_for_role", new=AsyncMock()
    ) as mock_get_top_countries:
        result = await _demand_context_line(cv_data, settings, db=None)

    assert result is None
    mock_get_top_countries.assert_not_called()


async def test_demand_context_line_returns_none_when_no_desired_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.workers.tasks.outreach import _demand_context_line

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_demand_intelligence_in_outreach", True)
    cv_data = CVData(desired_roles=[])

    with patch(
        "app.workers.tasks.outreach.get_top_countries_for_role", new=AsyncMock()
    ) as mock_get_top_countries:
        result = await _demand_context_line(cv_data, settings, db=None)

    assert result is None
    mock_get_top_countries.assert_not_called()


async def test_demand_context_line_returns_none_when_no_snapshot_data_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.workers.tasks.outreach import _demand_context_line

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_demand_intelligence_in_outreach", True)
    cv_data = CVData(desired_roles=["Backend Engineer", "Data Scientist"])

    with patch(
        "app.workers.tasks.outreach.get_top_countries_for_role",
        new=AsyncMock(return_value=[]),
    ) as mock_get_top_countries:
        result = await _demand_context_line(cv_data, settings, db=MagicMock())

    assert result is None
    assert mock_get_top_countries.call_count == 2


async def test_demand_context_line_returns_formatted_line_when_data_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.workers.tasks.outreach import _demand_context_line

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_demand_intelligence_in_outreach", True)
    cv_data = CVData(desired_roles=["Backend Engineer"])

    snapshots = [_fake_snapshot("us"), _fake_snapshot("de"), _fake_snapshot("nl")]
    with patch(
        "app.workers.tasks.outreach.get_top_countries_for_role",
        new=AsyncMock(return_value=snapshots),
    ):
        result = await _demand_context_line(cv_data, settings, db=MagicMock())

    assert result is not None
    assert "Backend Engineer" in result
    assert "US, DE, NL" in result


async def test_demand_context_line_falls_through_to_next_role_without_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First desired_roles entry has no snapshot data; the second does — this
    chunk's "first entry *with* data" contract, not strictly the first entry."""
    from app.workers.tasks.outreach import _demand_context_line

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_demand_intelligence_in_outreach", True)
    cv_data = CVData(desired_roles=["Nonexistent Role", "Backend Engineer"])

    snapshots = [_fake_snapshot("gb")]
    with patch(
        "app.workers.tasks.outreach.get_top_countries_for_role",
        new=AsyncMock(side_effect=[[], snapshots]),
    ):
        result = await _demand_context_line(cv_data, settings, db=MagicMock())

    assert result is not None
    assert "Backend Engineer" in result
    assert "GB" in result


async def test_draft_with_llm_includes_demand_context_line_when_flag_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "enable_demand_intelligence_in_outreach", True)
    cv_data = CVData(
        current_role="Engineer", technical_skills=["python"], desired_roles=["Backend Engineer"]
    )

    snapshots = [_fake_snapshot("us"), _fake_snapshot("de")]
    mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with (
        patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm),
        patch(
            "app.workers.tasks.outreach.get_top_countries_for_role",
            new=AsyncMock(return_value=snapshots),
        ),
    ):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "Acme context",
            "We need a Python expert.",
            settings,
            db=MagicMock(),
        )

    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    assert "highest current demand for Backend Engineer is in US, DE" in user_message


async def test_draft_with_llm_no_demand_context_line_when_no_snapshot_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "enable_demand_intelligence_in_outreach", True)
    cv_data = CVData(
        current_role="Engineer", technical_skills=["python"], desired_roles=["Backend Engineer"]
    )

    mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with (
        patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm),
        patch(
            "app.workers.tasks.outreach.get_top_countries_for_role",
            new=AsyncMock(return_value=[]),
        ),
    ):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "Acme context",
            "We need a Python expert.",
            settings,
            db=MagicMock(),
        )

    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    assert "Note: recent job-market data" not in user_message


async def test_draft_with_llm_no_demand_context_line_when_desired_roles_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "enable_demand_intelligence_in_outreach", True)
    cv_data = CVData(current_role="Engineer", technical_skills=["python"], desired_roles=[])

    mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with (
        patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm),
        patch(
            "app.workers.tasks.outreach.get_top_countries_for_role", new=AsyncMock()
        ) as mock_get_top_countries,
    ):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "Acme context",
            "We need a Python expert.",
            settings,
            db=MagicMock(),
        )

    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")
    assert "Note: recent job-market data" not in user_message
    mock_get_top_countries.assert_not_called()


async def test_draft_with_llm_does_not_query_demand_data_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release-blocking requirement: with the flag off (default), zero extra DB
    calls in `_draft_with_llm`'s code branch — not just zero prompt text."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "enable_demand_intelligence_in_outreach", False)
    cv_data = CVData(
        current_role="Engineer", technical_skills=["python"], desired_roles=["Backend Engineer"]
    )

    _mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with (
        patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm),
        patch(
            "app.workers.tasks.outreach.get_top_countries_for_role", new=AsyncMock()
        ) as mock_get_top_countries,
    ):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "Acme context",
            "We need a Python expert.",
            settings,
            db=MagicMock(),
        )

    mock_get_top_countries.assert_not_called()


async def test_draft_with_llm_user_content_byte_identical_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release-blocking regression: with `enable_demand_intelligence_in_outreach`
    off (the default), the constructed `user_content` for a given
    cv_data/company_name/role_title/context/job-description/message-type/strategy
    combination must be byte-identical to the pre-machine-2/07 output — this
    chunk must be a strict no-op for every existing caller/test that doesn't
    explicitly opt in via the new flag, and it must not depend on `db` being
    provided (passing `db=None`, exactly as every pre-existing call site in this
    test file above does, since none of them pass a `db` kwarg)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "enable_demand_intelligence_in_outreach", False)
    cv_data = CVData(
        current_role="Engineer",
        technical_skills=["python", "go"],
        total_years_experience=5.0,
        desired_roles=["Backend Engineer"],
    )

    mock_client, mock_client_cm = _mock_openai_client(
        '{"subject": "Hi Acme", "body": "Custom body"}'
    )
    with (
        patch("app.workers.tasks.outreach.httpx.AsyncClient", return_value=mock_client_cm),
        patch(
            "app.workers.tasks.outreach.get_top_countries_for_role", new=AsyncMock()
        ) as mock_get_top_countries,
    ):
        await _draft_with_llm(
            cv_data,
            "Acme",
            "Backend Engineer",
            "Acme context",
            "We need a Python expert.",
            settings,
            "email",
            None,
            "direct_pitch",
            None,
            None,
            None,
            None,
        )

    mock_get_top_countries.assert_not_called()
    sent_payload = mock_client.post.call_args.kwargs["json"]
    user_message = next(m["content"] for m in sent_payload["messages"] if m["role"] == "user")

    expected_user_content = (
        "Candidate background: Current role: Engineer. Skills: python, go. "
        "Years of experience: 5.0.\n"
        "Target company: Acme\n"
        "Target role: Backend Engineer\n"
        "Job description excerpt: We need a Python expert.\n"
        "Public company context: Acme context\n"
        f"{_STRATEGY_INSTRUCTIONS['direct_pitch']}"
    )
    assert user_message == expected_user_content


# --- Issue #4: cross-recruiter race on lazy company-tier classification ---


class _RaceLockRedis:
    """Minimal shared-state stand-in for the SET NX EX lock primitive used by
    both OutreachService.request_draft (service.py) and
    _classify_and_persist_company_tier (outreach.py). A plain dict is enough
    here since asyncio only ever interleaves at real `await` points, never
    truly in parallel."""

    def __init__(self) -> None:
        self._locks: dict[str, str] = {}

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool | None:
        if nx and key in self._locks:
            return None
        self._locks[key] = value
        return True

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if self._locks.pop(key, None) is not None:
                removed += 1
        return removed


async def test_classify_and_persist_company_tier_concurrent_calls_create_one_row(
    db: AsyncSession,
) -> None:
    """Issue #4 regression, exercised directly against the new locked helper
    (more deterministic than racing the full worker job through SQLite, whose
    own file-level locking otherwise masks the very TOCTOU window this lock
    exists to close).

    Explicit interleaving (not two purely sequential calls that never
    contend): the waiter coroutine is only released to start once the lock
    holder coroutine has *already* acquired the lock and is confirmed
    mid-classification (via an asyncio.Event set from inside the mocked
    classify_company_tier) -- so the waiter's own lock attempt is guaranteed
    to genuinely fail and fall into the poll loop, not race harmlessly before
    the holder ever touches the lock.
    """
    from app.workers.tasks.outreach import _classify_and_persist_company_tier

    shared_redis = _RaceLockRedis()
    holder_acquired = asyncio.Event()
    classify_calls: list[str] = []

    async def _slow_classify(name: str, context: str) -> str:
        classify_calls.append(name)
        holder_acquired.set()
        await asyncio.sleep(0.05)
        return "premium"

    company_name = f"RaceCo-{uuid4().hex[:8]}"

    async def _holder() -> EmployerCompanyTier:
        async with SessionLocal() as session:
            with patch(
                "app.workers.tasks.outreach.get_redis_connection", return_value=shared_redis
            ):
                with patch("app.workers.tasks.outreach.classify_company_tier", new=_slow_classify):
                    return await _classify_and_persist_company_tier(
                        session, company_name, "A tiny staffing shop."
                    )

    async def _waiter() -> EmployerCompanyTier:
        await holder_acquired.wait()  # only start once the holder genuinely owns the lock
        async with SessionLocal() as session:
            with patch(
                "app.workers.tasks.outreach.get_redis_connection", return_value=shared_redis
            ):
                with patch("app.workers.tasks.outreach.classify_company_tier", new=_slow_classify):
                    return await _classify_and_persist_company_tier(
                        session, company_name, "A tiny staffing shop."
                    )

    holder_result, waiter_result = await asyncio.gather(_holder(), _waiter())

    # Both calls complete without raising (asserted implicitly by gather not
    # propagating an exception) and both resolve to the SAME persisted row.
    assert holder_result.tier == "premium"
    assert waiter_result.id == holder_result.id

    # Only the lock holder actually ran the classifier -- the waiter's poll
    # loop found the holder's committed row and reused it, proving the lock
    # (not luck) is what prevented a duplicate insert.
    assert classify_calls == [company_name]

    # Lock must not be left held after the holder releases it.
    assert shared_redis._locks == {}

    async with SessionLocal() as verify_session:
        all_rows = await verify_session.execute(
            select(EmployerCompanyTier).where(EmployerCompanyTier.company_name == company_name)
        )
        assert len(all_rows.scalars().all()) == 1


async def test_classify_and_persist_company_tier_falls_back_to_classifying_locally_on_timeout(
    db: AsyncSession,
) -> None:
    """Bounded-wait fallback: if the lock is held (e.g. the original holder
    crashed) and never releases within the poll budget, the waiter must NOT
    block indefinitely -- it falls back to classifying locally itself."""
    from app.workers.tasks.outreach import (
        _COMPANY_TIER_LOCK_POLL_INTERVAL_SECONDS,
        _classify_and_persist_company_tier,
    )

    shared_redis = _RaceLockRedis()
    company_name = f"StaleCo-{uuid4().hex[:8]}"
    # Simulate a lock that is held by a (crashed) other worker and never released.
    lock_key = f"company-tier-classify-lock:{company_name.strip().lower()}"
    shared_redis._locks[lock_key] = "1"

    with (
        patch("app.workers.tasks.outreach.get_redis_connection", return_value=shared_redis),
        patch(
            "app.workers.tasks.outreach.classify_company_tier",
            new=AsyncMock(return_value="outsourcing"),
        ) as mock_classify,
        patch("app.workers.tasks.outreach.asyncio.sleep", new=AsyncMock()),
    ):
        result = await _classify_and_persist_company_tier(db, company_name, "context")

    mock_classify.assert_awaited_once_with(company_name, "context")
    assert result.tier == "outsourcing"

    persisted = await db.execute(
        select(EmployerCompanyTier).where(EmployerCompanyTier.company_name == company_name)
    )
    assert len(persisted.scalars().all()) == 1
    # The stale lock is left in place (this caller never held it, only the
    # original -- now-gone -- holder could release it, or it expires via its
    # own TTL); irrelevant to _COMPANY_TIER_LOCK_POLL_INTERVAL_SECONDS import
    # above other than confirming the constant this test's docstring refers
    # to actually exists and is imported from the real module.
    assert _COMPANY_TIER_LOCK_POLL_INTERVAL_SECONDS > 0
