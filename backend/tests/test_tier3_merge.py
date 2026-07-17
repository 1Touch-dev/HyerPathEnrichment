from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import get_settings
from app.enrichers.email_verify import EmailVerifyEnricher
from app.domain.enrichment import EnrichmentRequest
from app.providers import EmailVerifier
from app.enrichers.pipeline import Pipeline


@pytest.fixture
def orchestrator() -> Pipeline:
    return Pipeline(db=MagicMock())


def test_collect_email_candidates_dedupes_and_normalizes(orchestrator: Pipeline) -> None:
    request = EnrichmentRequest(
        email="A@GitHub.com",
        username="torvalds",
        company="github",
        requested_tiers=["tier3"],
    )
    payloads = [
        {"emails": ["b@github.com", "a@github.com"]},
        {"emails": ["c@github.com"]},
    ]
    candidates = orchestrator._collect_email_candidates(request, payloads)
    assert candidates == ["a@github.com", "b@github.com", "c@github.com"]


def test_collect_email_candidates_synthetic_when_empty(orchestrator: Pipeline) -> None:
    request = EnrichmentRequest(username="jane", company="Acme Corp", requested_tiers=["tier3"])
    candidates = orchestrator._collect_email_candidates(request, [])
    assert candidates == ["jane@acmecorp.com"]


def test_collect_email_candidates_respects_cap(
    orchestrator: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "email_verify_max_per_job", 2)
    request = EnrichmentRequest(
        email="one@example.com",
        username="jane",
        company="example",
        requested_tiers=["tier3"],
    )
    payloads = [{"emails": ["two@example.com", "three@example.com"]}]
    candidates = orchestrator._collect_email_candidates(request, payloads)
    assert candidates == ["one@example.com", "two@example.com"]


async def test_verify_email_batch_delegates_to_enricher(orchestrator: Pipeline) -> None:
    expected = {
        "verified_emails": [{"value": "a@b.com", "status": "deliverable", "confidence": 0.8, "source": "mx"}],
        "sources": ["Email Verify"],
    }
    orchestrator._email_verify.verify_emails = AsyncMock(return_value=expected)
    payload = await orchestrator._verify_email_batch(["a@b.com"])
    assert payload == expected


async def test_verify_emails_returns_multiple(orchestrator: Pipeline) -> None:
    async def _verify(email: str):
        return {
            "value": email,
            "status": "deliverable",
            "confidence": 0.55,
            "source": "mx",
        }

    enricher = EmailVerifyEnricher()
    enricher.verifier.verify = _verify  # type: ignore[method-assign]
    payload = await enricher.verify_emails(["a@example.com", "b@example.com"])
    assert len(payload["verified_emails"]) == 2
    assert payload["sources"] == ["Email Verify"]


async def test_basic_mode_skips_reacher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "email_verify_level", "basic")

    async def _reacher_should_not_run(self, url: str, email: str):
        raise AssertionError("Reacher must not run in basic mode")

    monkeypatch.setattr(EmailVerifier, "_reacher", _reacher_should_not_run)
    result = await EmailVerifier().verify("user@example.com")
    assert result is not None
    assert result["source"] in {"syntax", "mx", "AfterShip Email Verifier"}


async def test_smtp_mode_calls_reacher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "email_verify_level", "smtp")
    monkeypatch.setattr(get_settings(), "reacher_url", "http://reacher:8080")

    async def _no_mx(self, domain: str):
        return None

    async def _no_aftership(self, url: str, email: str):
        return None

    reacher_called = False

    async def _reacher(self, url: str, email: str):
        nonlocal reacher_called
        reacher_called = True
        return {"status": "verified", "confidence": 0.95, "source": "Reacher"}

    monkeypatch.setattr(EmailVerifier, "_mx_ok", _no_mx)
    monkeypatch.setattr(EmailVerifier, "_aftership", _no_aftership)
    monkeypatch.setattr(EmailVerifier, "_reacher", _reacher)

    result = await EmailVerifier().verify("user@example.com")
    assert reacher_called is True
    assert result["source"] == "Reacher"


async def test_smtp_skips_aftership_when_reacher_conclusive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "email_verify_level", "smtp")
    monkeypatch.setattr(get_settings(), "reacher_url", "http://reacher:8080")

    async def _no_mx(self, domain: str):
        return None

    async def _aftership_should_not_run(self, url: str, email: str):
        raise AssertionError("AfterShip must not run when Reacher is conclusive")

    async def _reacher(self, url: str, email: str):
        return {"status": "verified", "confidence": 0.95, "source": "Reacher"}

    monkeypatch.setattr(EmailVerifier, "_mx_ok", _no_mx)
    monkeypatch.setattr(EmailVerifier, "_aftership", _aftership_should_not_run)
    monkeypatch.setattr(EmailVerifier, "_reacher", _reacher)

    result = await EmailVerifier().verify("user@example.com")
    assert result["source"] == "Reacher"
    assert result["status"] == "verified"


async def test_smtp_falls_back_to_aftership_when_reacher_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "email_verify_level", "smtp")
    monkeypatch.setattr(get_settings(), "reacher_url", "http://reacher:8080")
    monkeypatch.setattr(get_settings(), "email_verifier_url", "http://email-verifier:8080")

    async def _no_mx(self, domain: str):
        return None

    async def _reacher(self, url: str, email: str):
        return {"status": "unknown", "confidence": 0.3, "source": "Reacher"}

    aftership_called = False

    async def _aftership(self, url: str, email: str):
        nonlocal aftership_called
        aftership_called = True
        return {
            "status": "deliverable",
            "confidence": 0.8,
            "source": "AfterShip Email Verifier",
        }

    monkeypatch.setattr(EmailVerifier, "_mx_ok", _no_mx)
    monkeypatch.setattr(EmailVerifier, "_reacher", _reacher)
    monkeypatch.setattr(EmailVerifier, "_aftership", _aftership)

    result = await EmailVerifier().verify("user@example.com")
    assert aftership_called is True
    assert result["source"] == "AfterShip Email Verifier"
    assert result["status"] == "deliverable"


async def test_smtp_falls_back_to_aftership_when_reacher_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "email_verify_level", "smtp")
    monkeypatch.setattr(get_settings(), "reacher_url", "http://reacher:8080")
    monkeypatch.setattr(get_settings(), "email_verifier_url", "http://email-verifier:8080")

    async def _no_mx(self, domain: str):
        return None

    async def _reacher_unreachable(self, url: str, email: str):
        return None

    aftership_called = False

    async def _aftership(self, url: str, email: str):
        nonlocal aftership_called
        aftership_called = True
        return {
            "status": "deliverable",
            "confidence": 0.8,
            "source": "AfterShip Email Verifier",
        }

    monkeypatch.setattr(EmailVerifier, "_mx_ok", _no_mx)
    monkeypatch.setattr(EmailVerifier, "_reacher", _reacher_unreachable)
    monkeypatch.setattr(EmailVerifier, "_aftership", _aftership)

    result = await EmailVerifier().verify("user@example.com")
    assert aftership_called is True
    assert result["source"] == "AfterShip Email Verifier"


async def test_reacher_catch_all_surfaces_low_trust(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "email_verify_level", "smtp")
    monkeypatch.setattr(get_settings(), "reacher_url", "http://reacher:8080")

    async def _no_mx(self, domain: str):
        return None

    async def _aftership_should_not_run(self, url: str, email: str):
        raise AssertionError("AfterShip must not run when Reacher reports catch-all")

    from app.providers import sidecar as sidecar_mod

    async def _post_json(self, path="", json=None):
        return {
            "is_reachable": "risky",
            "misc": {"is_catch_all": True},
            "smtp": {"is_catch_all": True, "is_deliverable": True},
        }

    monkeypatch.setattr(EmailVerifier, "_mx_ok", _no_mx)
    monkeypatch.setattr(EmailVerifier, "_aftership", _aftership_should_not_run)
    monkeypatch.setattr(sidecar_mod.SidecarClient, "post_json", _post_json)

    result = await EmailVerifier().verify("guess@catchall.example.com")
    assert result["status"] == "catch_all"
    assert result["source"] == "Reacher"
    assert result["confidence"] < 0.5


async def test_tier3_dispatch_runs_verify_after_discover(
    orchestrator: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discover_payload = {"emails": ["found@github.com"], "sources": ["theHarvester"]}
    verify_payload = {
        "verified_emails": [
            {"value": "found@github.com", "status": "deliverable", "confidence": 0.8, "source": "mx"}
        ],
        "sources": ["Email Verify"],
    }

    async def _run_discover(_enrichers, _request):
        return [discover_payload]

    orchestrator._run_tier_parallel = AsyncMock(side_effect=_run_discover)
    orchestrator._email_verify.verify_emails = AsyncMock(return_value=verify_payload)

    request = EnrichmentRequest(
        username="torvalds",
        company="github",
        requested_tiers=["tier3"],
    )
    payloads = await orchestrator._dispatch(request, sync_mode=True)

    assert discover_payload in payloads
    assert verify_payload in payloads
    orchestrator._email_verify.verify_emails.assert_awaited_once()
    called_emails = orchestrator._email_verify.verify_emails.await_args.args[0]
    assert "found@github.com" in called_emails
