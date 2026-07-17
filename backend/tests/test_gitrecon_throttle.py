"""GitRecon GitHub throttle / rate-limit soft-fail tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.enrichers import gitrecon as gitrecon_mod
from app.enrichers.gitrecon import GitReconEnricher, _looks_like_github_rate_limit
from app.domain.enrichment import EnrichmentRequest
from tests.conftest import FakeRedis


@pytest.fixture
def gitrecon_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    fake = FakeRedis()
    monkeypatch.setattr(gitrecon_mod, "get_redis_client", lambda: fake)
    return fake


def test_looks_like_github_rate_limit_detects_markers() -> None:
    assert _looks_like_github_rate_limit("HTTP 403 Forbidden")
    assert _looks_like_github_rate_limit("status 429 Too Many Requests")
    assert _looks_like_github_rate_limit("API rate limit exceeded")
    assert _looks_like_github_rate_limit("secondary rate-limit")
    assert _looks_like_github_rate_limit("Abuse Detection Mechanism")
    assert not _looks_like_github_rate_limit("user not found")
    assert not _looks_like_github_rate_limit("")


async def test_gitrecon_rate_limit_stderr_soft_fails(
    monkeypatch: pytest.MonkeyPatch, gitrecon_redis: FakeRedis
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gitrecon_script", "")
    monkeypatch.setattr(settings, "gitrecon_rate_limit_backoff_seconds", 0)
    monkeypatch.setattr(settings, "gitrecon_cooldown_seconds", 60)
    monkeypatch.setattr(settings, "github_token", "test-token")

    async def _run(args, timeout, env=None, cwd=None):
        assert env is not None
        assert env.get("GITHUB_TOKEN") == "test-token"
        return 1, "", "Error: API rate limit exceeded (HTTP 403)"

    slept: list[float] = []

    async def _sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(gitrecon_mod, "run_command", _run)
    monkeypatch.setattr(gitrecon_mod.asyncio, "sleep", _sleep)

    fragment = await GitReconEnricher().run(EnrichmentRequest(username="octocat", requested_tiers=["tier3"]))
    assert fragment == {}
    assert await gitrecon_redis.get(gitrecon_mod._COOLDOWN_KEY) == "1"
    # backoff configured to 0 so sleep is skipped
    assert slept == []


async def test_gitrecon_rate_limit_brief_backoff(
    monkeypatch: pytest.MonkeyPatch, gitrecon_redis: FakeRedis
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gitrecon_rate_limit_backoff_seconds", 2.5)
    monkeypatch.setattr(settings, "gitrecon_cooldown_seconds", 30)

    async def _run(args, timeout, env=None, cwd=None):
        return 1, "", "GitHub API 429: too many requests"

    slept: list[float] = []

    async def _sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(gitrecon_mod, "run_command", _run)
    monkeypatch.setattr(gitrecon_mod.asyncio, "sleep", _sleep)

    fragment = await GitReconEnricher().run(EnrichmentRequest(username="octocat", requested_tiers=["tier3"]))
    assert fragment == {}
    assert slept == [2.5]


async def test_gitrecon_skips_when_cooldown_active(
    monkeypatch: pytest.MonkeyPatch, gitrecon_redis: FakeRedis
) -> None:
    await gitrecon_redis.set(gitrecon_mod._COOLDOWN_KEY, "1", ex=60)
    called = False

    async def _run(*args, **kwargs):
        nonlocal called
        called = True
        return 0, "", ""

    monkeypatch.setattr(gitrecon_mod, "run_command", _run)
    fragment = await GitReconEnricher().run(EnrichmentRequest(username="octocat", requested_tiers=["tier3"]))
    assert fragment == {}
    assert called is False


async def test_gitrecon_skips_when_per_minute_exhausted(
    monkeypatch: pytest.MonkeyPatch, gitrecon_redis: FakeRedis
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gitrecon_max_per_minute", 1)

    async def _run(args, timeout, env=None, cwd=None):
        payload = {"username": "octocat", "orgs": [], "leaked_emails": []}
        result = Path(cwd) / "results" / "octocat" / "octocat_github.json"
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text(json.dumps(payload), encoding="utf-8")
        return 0, "", ""

    monkeypatch.setattr(gitrecon_mod, "run_command", _run)

    first = await GitReconEnricher().run(EnrichmentRequest(username="octocat", requested_tiers=["tier3"]))
    assert first["handles"][0]["username"] == "octocat"

    second = await GitReconEnricher().run(EnrichmentRequest(username="octocat", requested_tiers=["tier3"]))
    assert second == {}


async def test_gitrecon_normal_path_parses_json(
    monkeypatch: pytest.MonkeyPatch, gitrecon_redis: FakeRedis
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gitrecon_script", "")
    monkeypatch.setattr(settings, "github_token", "tok")
    payload = {
        "username": "octocat",
        "orgs": ["github"],
        "leaked_emails": ["octocat@github.com"],
    }

    async def _run(args, timeout, env=None, cwd=None):
        assert env.get("GITHUB_TOKEN") == "tok"
        result = Path(cwd) / "results" / "octocat" / "octocat_github.json"
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text(json.dumps(payload), encoding="utf-8")
        return 0, "", ""

    monkeypatch.setattr(gitrecon_mod, "run_command", _run)
    fragment = await GitReconEnricher().run(EnrichmentRequest(username="octocat", requested_tiers=["tier3"]))
    assert fragment["handles"][0]["platform"] == "GitHub"
    assert fragment["github"]["organizations"] == ["github"]
    assert fragment["emails"] == ["octocat@github.com"]
    assert fragment["sources"] == ["GitRecon"]
