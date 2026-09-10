"""Pipeline contract tests: partial failure, tier dispatch, validation, suppression."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.database.session import SessionLocal, init_db
from app.domain.dossier import Dossier
from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import RequestedTier
from app.enrichers import (
    JobSpyEnricher,
    MaigretEnricher,
    SherlockEnricher,
    SocialAnalyzerEnricher,
)
from app.enrichers import pipeline as pipeline_mod
from app.enrichers.base import Enricher
from app.enrichers.pipeline import Pipeline
from app.main import app
from app.modules.enrichment import service as enrichment_service


def _stub(fragment: dict[str, Any]):
    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        return dict(fragment)

    return _fetch


def _tier_validation_enabled() -> bool:
    try:
        EnrichmentRequest(username="candidate", requested_tiers=[RequestedTier.tier1])
    except ValidationError as exc:
        return any("tier1 requires linkedin_url" in str(error["msg"]) for error in exc.errors())
    return False


@pytest.fixture(autouse=True)
def _offline_enrichers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        SherlockEnricher,
        "_fetch",
        _stub(
            {
                "handles": [
                    {
                        "platform": "X",
                        "username": "candidate",
                        "profile_url": "https://x.com/candidate",
                        "confidence": 0.75,
                        "metadata": {"provider": "Sherlock", "matched": True},
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        MaigretEnricher,
        "_fetch",
        _stub(
            {
                "handles": [
                    {
                        "platform": "Reddit",
                        "username": "candidate",
                        "profile_url": "https://reddit.com/u/candidate",
                        "confidence": 0.71,
                        "metadata": {"provider": "Maigret", "matched": True},
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        SocialAnalyzerEnricher,
        "_fetch",
        _stub(
            {
                "handles": [
                    {
                        "platform": "Linkedin",
                        "username": "candidate",
                        "profile_url": "https://linkedin.com/in/candidate",
                        "confidence": 0.88,
                        "metadata": {"provider": "Social Analyzer", "matched": True},
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        JobSpyEnricher,
        "_fetch",
        _stub(
            {
                "jobs": [
                    {
                        "title": "Staff Backend Engineer",
                        "company": "Hyrepath Labs",
                        "location": "Remote",
                        "remote": True,
                        "source": "JobSpy",
                    }
                ]
            }
        ),
    )


class _BoomEnricher(Enricher):
    source_name = "Boom"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return True

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        raise RuntimeError("backend down")


@pytest.mark.asyncio
async def test_sync_run_persists_job_before_external_execution() -> None:
    events: list[str] = []
    job = object()
    pipeline = Pipeline(db=object())  # type: ignore[arg-type]

    async def _create(*_args: Any, **_kwargs: Any) -> object:
        events.append("create")
        return job

    async def _mark_status(*_args: Any, **_kwargs: Any) -> object:
        events.append("mark_status")
        return job

    async def _execute(*_args: Any, **_kwargs: Any) -> object:
        events.append("execute")
        return job

    pipeline.jobs.create = _create  # type: ignore[method-assign]
    pipeline.jobs.mark_status = _mark_status  # type: ignore[method-assign]
    pipeline._execute = _execute  # type: ignore[method-assign]

    result = await pipeline.run(
        EnrichmentRequest(username="pipeline-user", requested_tiers=["tier2"])
    )

    assert result is job
    assert events == ["create", "mark_status", "execute"]


@pytest.mark.asyncio
async def test_execute_closes_suppression_read_transaction_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    job = object()
    pipeline = Pipeline(db=object())  # type: ignore[arg-type]

    async def _is_suppressed(*_args: Any, **_kwargs: Any) -> bool:
        events.append("suppression_check")
        return False

    async def _commit() -> None:
        events.append("commit")

    async def _dispatch(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        events.append("dispatch")
        return []

    async def _merge(*_args: Any, **_kwargs: Any) -> Dossier:
        return Dossier()

    async def _mark_status(*_args: Any, **_kwargs: Any) -> object:
        return job

    monkeypatch.setattr(pipeline_mod, "is_request_suppressed", _is_suppressed)
    pipeline.jobs.commit = _commit  # type: ignore[method-assign]
    pipeline.jobs.mark_status = _mark_status  # type: ignore[method-assign]
    pipeline._dispatch = _dispatch  # type: ignore[method-assign]
    pipeline._merge = _merge  # type: ignore[method-assign]

    await pipeline._execute(
        job,  # type: ignore[arg-type]
        EnrichmentRequest(username="pipeline-user", requested_tiers=["tier2"]),
        sync_mode=True,
    )

    assert events == ["suppression_check", "commit", "dispatch"]


@pytest.mark.asyncio
async def test_partial_failure_one_enricher_raises() -> None:
    await init_db()
    async with SessionLocal() as session:
        orchestrator = Pipeline(session)
        orchestrator.tier2 = [SherlockEnricher(), _BoomEnricher(), SocialAnalyzerEnricher()]
        request = EnrichmentRequest(username="pipeline-user", requested_tiers=["tier2"])
        result = await orchestrator.run(request)
        assert result.status == "completed"
        platforms = {handle["platform"] for handle in result.dossier_payload["handles"]}
        assert "X" in platforms
        assert "Linkedin" in platforms


def test_multi_tier_dispatch_respects_selection(
    staff_auth_headers: dict[str, str],
) -> None:
    client = TestClient(app)
    response = client.post(
        "/enrich/sync",
        headers=staff_auth_headers,
        json={
            "username": "candidate",
            "job_search": "Staff Backend Engineer",
            "requested_tiers": ["tier2", "tier4"],
        },
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "completed"
    assert payload["dossier"]["handles"]
    assert payload["dossier"]["jobs"]
    assert payload["dossier"]["verified_emails"] == []
    assert payload["dossier"]["coworkers"] == []


def test_tier1_skipped_on_sync_path(
    monkeypatch: pytest.MonkeyPatch, staff_auth_headers: dict[str, str]
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_tier1", True)
    client = TestClient(app)
    response = client.post(
        "/enrich/sync",
        headers=staff_auth_headers,
        json={
            "linkedin_url": "https://linkedin.com/in/candidate",
            "username": "candidate",
            "requested_tiers": ["tier1", "tier2"],
        },
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "completed"
    assert payload["dossier"]["photo"] is None


@pytest.mark.xfail(not _tier_validation_enabled(), reason="requires task 51", strict=False)
def test_invalid_tier1_without_linkedin_422(
    staff_auth_headers: dict[str, str],
) -> None:
    client = TestClient(app)
    response = client.post(
        "/enrich/sync",
        headers=staff_auth_headers,
        json={"username": "candidate", "requested_tiers": ["tier1"]},
    )
    assert response.status_code == 422
    assert "tier1 requires linkedin_url" in response.text


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        ({"email": "user@example.com", "requested_tiers": ["tier2"]}, "tier2 requires username"),
        (
            {"business": "Acme", "requested_tiers": ["tier3"]},
            "tier3 requires at least one of username, email, or company",
        ),
        (
            {"username": "candidate", "requested_tiers": ["tier4"]},
            "tier4 requires at least one of job_search or business",
        ),
    ],
)
@pytest.mark.xfail(not _tier_validation_enabled(), reason="requires task 51", strict=False)
def test_tier_validation_rules(payload: dict[str, Any], expected_message: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        EnrichmentRequest(**payload)
    assert expected_message in str(exc_info.value.errors()[0]["msg"])


def test_suppressed_async_and_sync(staff_auth_headers: dict[str, str]) -> None:
    client = TestClient(app)
    identifier = "contracts-suppressed@example.com"

    client.post("/api/opt-out", json={"identifier": identifier, "reason": "gdpr"})

    async_resp = client.post(
        "/enrich",
        headers=staff_auth_headers,
        json={"email": identifier, "username": "ignored", "requested_tiers": ["tier2"]},
    )
    assert async_resp.status_code == 202
    assert async_resp.json()["data"]["status"] == "suppressed"

    sync_resp = client.post(
        "/enrich/sync",
        headers=staff_auth_headers,
        json={"email": identifier, "username": "ignored", "requested_tiers": ["tier2"]},
    )
    assert sync_resp.status_code == 200
    assert sync_resp.json()["data"]["status"] == "suppressed"


def test_async_enrich_suppressed_skips_enqueue(
    monkeypatch: pytest.MonkeyPatch, staff_auth_headers: dict[str, str]
) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(
        enrichment_service,
        "enqueue_enrichment",
        lambda job_id, *args, **kwargs: enqueued.append(job_id),
    )

    client = TestClient(app)
    identifier = "contracts-async-skip@example.com"
    client.post("/api/opt-out", json={"identifier": identifier, "reason": "gdpr"})

    response = client.post(
        "/enrich",
        headers=staff_auth_headers,
        json={"email": identifier, "username": "ignored", "requested_tiers": ["tier2"]},
    )
    assert response.status_code == 202
    assert response.json()["data"]["status"] == "suppressed"
    assert enqueued == []
