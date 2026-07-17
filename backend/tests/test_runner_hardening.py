"""Orchestrator failure isolation and sidecar retry behavior."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.enrichers.base import Enricher
from app.models import EnrichmentRequest
from app.providers.retry import is_transient_http_error, with_transient_retry
from app.providers.sidecar import SidecarClient
from app.enrichers.pipeline import Pipeline


@pytest.fixture
def orchestrator() -> Pipeline:
    return Pipeline(db=MagicMock())


class _BoomInit(Enricher):
    source_name = "BoomInit"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return True

    async def initialize(self) -> None:
        raise RuntimeError("init failed")

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        return {}


class _BoomScore(Enricher):
    source_name = "BoomScore"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return True

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        return {"handles": [{"platform": "X", "username": "ok", "profile_url": "https://x.com/ok", "confidence": 0.8}]}

    async def score(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("score failed")


class _OkEnricher(Enricher):
    source_name = "Ok"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return True

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        return {
            "handles": [
                {
                    "platform": "GitHub",
                    "username": "ok-user",
                    "profile_url": "https://github.com/ok-user",
                    "confidence": 0.9,
                }
            ]
        }


@pytest.mark.asyncio
async def test_invoke_enricher_returns_empty_on_initialize_failure(
    orchestrator: Pipeline,
) -> None:
    payload = await orchestrator._invoke_enricher(
        _BoomInit(), EnrichmentRequest(username="jane", requested_tiers=["tier2"])
    )
    assert payload == {}


@pytest.mark.asyncio
async def test_invoke_enricher_returns_empty_on_score_failure(
    orchestrator: Pipeline,
) -> None:
    payload = await orchestrator._invoke_enricher(
        _BoomScore(), EnrichmentRequest(username="jane", requested_tiers=["tier2"])
    )
    assert payload == {}


@pytest.mark.asyncio
async def test_parallel_tier_keeps_sibling_payload_on_failure(
    orchestrator: Pipeline,
) -> None:
    results = await orchestrator._run_tier_parallel(
        [_BoomScore(), _OkEnricher()],
        EnrichmentRequest(username="jane", requested_tiers=["tier2"]),
    )
    assert len(results) == 2
    assert results[0] == {}
    assert results[1]["handles"][0]["username"] == "ok-user"


@pytest.mark.asyncio
async def test_execute_job_completes_when_one_tier2_enricher_fails() -> None:
    from app.database.session import SessionLocal, init_db

    await init_db()
    async with SessionLocal() as session:
        local = Pipeline(db=session)
        local.tier2 = [_BoomScore(), _OkEnricher()]
        request = EnrichmentRequest(username="worker-user", requested_tiers=["tier2"])
        job = await local.create_queued_job(request)
        result = await local.execute_job(job.id)
        assert result is not None
        assert result.status == "completed"
        assert any(h["username"] == "ok-user" for h in result.dossier_payload["handles"])


def test_is_transient_http_error_detects_connect_and_503() -> None:
    assert is_transient_http_error(httpx.ConnectError("down"))
    response = httpx.Response(503, request=httpx.Request("GET", "http://example"))
    assert is_transient_http_error(httpx.HTTPStatusError("bad", request=response.request, response=response))
    response_400 = httpx.Response(400, request=httpx.Request("GET", "http://example"))
    assert not is_transient_http_error(
        httpx.HTTPStatusError("bad", request=response_400.request, response=response_400)
    )


@pytest.mark.asyncio
async def test_with_transient_retry_retries_then_succeeds() -> None:
    calls = {"count": 0}

    async def flaky() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise httpx.ConnectError("down")
        return "ok"

    result = await with_transient_retry(flaky, max_retries=2)
    assert result == "ok"
    assert calls["count"] == 3


@pytest.mark.asyncio
async def test_sidecar_get_json_retries_transient_failure() -> None:
    client = SidecarClient("http://sidecar:8080", timeout=1.0)
    calls = {"count": 0}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"ok": "true"}

    class _FakeHttpClient:
        async def __aenter__(self) -> "_FakeHttpClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, *_args: object, **_kwargs: object) -> _FakeResponse:
            calls["count"] += 1
            if calls["count"] == 1:
                raise httpx.ConnectError("down")
            return _FakeResponse()

    with patch("app.clients.sidecar.httpx.AsyncClient", return_value=_FakeHttpClient()):
        payload = await client.get_json("/health")

    assert payload == {"ok": "true"}
    assert calls["count"] == 2
