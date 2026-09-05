"""Tests for the heuristic + LLM-judge moderation flagging cascade (Batch 1).

Mocking pattern for the LLM call mirrors test_cv_extraction.py's
`patch("...httpx.AsyncClient")` shape, since moderation_flagging.run_llm_judge
reuses cv_extractor.py's exact httpx.AsyncClient + OpenAI JSON-mode call.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from app.modules.admin.models import AdminReviewQueueItem
from app.modules.admin.moderation_flagging import (
    flag_if_needed,
    run_heuristic_check,
    run_llm_judge,
)

# NOTE: no module-level pytestmark = pytest.mark.asyncio here — this file
# mixes sync and async test functions, and pyproject.toml's asyncio_mode =
# "auto" already handles async def tests automatically (see
# test_admin_rbac.py's identical rationale).


def test_run_heuristic_check_catches_deny_listed_term():
    reason = run_heuristic_check(["Check this out", "GUARANTEED INCOME for everyone!"])
    assert reason is not None
    assert "guaranteed income" in reason.lower()


def test_run_heuristic_check_returns_none_for_clean_text():
    assert run_heuristic_check(["Experienced backend engineer", "5 years of Python"]) is None


async def test_flag_if_needed_creates_heuristic_row(db_session):
    resource_id = uuid4()
    item = await flag_if_needed(
        db_session,
        resource_type="job_posting",
        resource_id=resource_id,
        text_fields=["Buy followers now!!", "click here to win a prize"],
    )

    assert item is not None
    assert item.flag_source == "heuristic"
    assert item.status == "pending"
    assert item.resource_id == resource_id

    from sqlalchemy import select

    result = await db_session.execute(
        select(AdminReviewQueueItem).where(AdminReviewQueueItem.resource_id == resource_id)
    )
    persisted = result.scalar_one()
    assert persisted.flag_source == "heuristic"


async def test_flag_if_needed_falls_back_to_llm_judge_when_heuristic_clean(db_session):
    resource_id = uuid4()
    with patch(
        "app.modules.admin.moderation_flagging.run_llm_judge",
        new=AsyncMock(return_value=(True, "policy violation: harassment")),
    ):
        item = await flag_if_needed(
            db_session,
            resource_type="document",
            resource_id=resource_id,
            text_fields=["A perfectly normal-looking cover letter"],
        )

    assert item is not None
    assert item.flag_source == "llm_judge"
    assert item.flag_reason == "policy violation: harassment"


async def test_flag_if_needed_returns_none_when_neither_check_flags(db_session):
    resource_id = uuid4()
    with patch(
        "app.modules.admin.moderation_flagging.run_llm_judge",
        new=AsyncMock(return_value=(False, None)),
    ):
        item = await flag_if_needed(
            db_session,
            resource_type="document",
            resource_id=resource_id,
            text_fields=["A perfectly normal-looking cover letter"],
        )

    assert item is None


async def test_flag_if_needed_fails_open_when_llm_judge_raises(db_session):
    resource_id = uuid4()
    with patch(
        "app.modules.admin.moderation_flagging.run_llm_judge",
        new=AsyncMock(side_effect=TimeoutError("simulated API timeout")),
    ):
        item = await flag_if_needed(
            db_session,
            resource_type="document",
            resource_id=resource_id,
            text_fields=["A perfectly normal-looking cover letter"],
        )

    assert item is None


async def test_run_llm_judge_returns_flagged_true_on_success():
    mock_response = {
        "choices": [{"message": {"content": '{"flagged": true, "reason": "spam content"}'}}]
    }

    with patch("app.modules.admin.moderation_flagging.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = "test-key-123"
        with patch("app.modules.admin.moderation_flagging.httpx.AsyncClient") as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.json = Mock(return_value=mock_response)
            mock_response_obj.raise_for_status = lambda: None

            mock_post = AsyncMock(return_value=mock_response_obj)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            flagged, reason = await run_llm_judge("document", ["some text"])

    assert flagged is True
    assert reason == "spam content"


async def test_run_llm_judge_fails_open_on_missing_api_key():
    with patch("app.modules.admin.moderation_flagging.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = ""
        flagged, reason = await run_llm_judge("document", ["some text"])

    assert flagged is False
    assert reason is None


async def test_run_llm_judge_fails_open_on_http_error():
    with patch("app.modules.admin.moderation_flagging.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = "test-key-123"
        with patch("app.modules.admin.moderation_flagging.httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(side_effect=Exception("network error"))
            mock_client.return_value.__aenter__.return_value.post = mock_post

            flagged, reason = await run_llm_judge("document", ["some text"])

    assert flagged is False
    assert reason is None


async def test_run_llm_judge_fails_open_on_malformed_json():
    mock_response = {"choices": [{"message": {"content": "not valid json"}}]}

    with patch("app.modules.admin.moderation_flagging.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = "test-key-123"
        with patch("app.modules.admin.moderation_flagging.httpx.AsyncClient") as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.json = Mock(return_value=mock_response)
            mock_response_obj.raise_for_status = lambda: None

            mock_post = AsyncMock(return_value=mock_response_obj)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            flagged, reason = await run_llm_judge("document", ["some text"])

    assert flagged is False
    assert reason is None
