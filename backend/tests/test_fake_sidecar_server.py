"""Contract tests for fake sidecar HTTP mocks (no Docker required)."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import httpx
import pytest

from app.core.config import get_settings
from app.enrichers.local_business import LocalBusinessEnricher
from app.enrichers.social_analyzer import SocialAnalyzerEnricher
from app.domain.enrichment import EnrichmentRequest
from app.clients.email_verify import EmailVerifier

FAKE_ROOT = Path(__file__).resolve().parents[1] / "docker" / "fake-sidecars"
if str(FAKE_ROOT) not in sys.path:
    sys.path.insert(0, str(FAKE_ROOT))


def _load_app(mode: str):
    os.environ["FAKE_SIDECAR"] = mode
    import server as fake_server

    importlib.reload(fake_server)
    return fake_server.app


@pytest.mark.asyncio
async def test_fake_social_analyzer_contract() -> None:
    app = _load_app("social-analyzer")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        settings = await client.get("/get_settings")
        analyze = await client.post("/analyze_string", json={"string": "torvalds"})

    assert settings.status_code == 200
    assert "websites" in settings.json()
    assert analyze.status_code == 200
    detected = analyze.json().get("user_info_normal", {}).get("data", [])
    assert len(detected) == 3


@pytest.mark.asyncio
async def test_fake_social_analyzer_enricher_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _load_app("social-analyzer")
    transport = httpx.ASGITransport(app=app)

    async def _request(self, method: str, url: str, **kwargs):
        path = url.replace(self.base_url, "") or "/"
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.request(method, path, **kwargs)
        response.raise_for_status()
        if "download" in path:
            return response.text
        return response.json()

    from app.clients import sidecar as sidecar_mod

    async def _post_json(self, path="", json=None):
        return await _request(self, "POST", f"{self.base_url}{path}", json=json)

    monkeypatch.setattr(get_settings(), "social_analyzer_url", "http://test")
    monkeypatch.setattr(sidecar_mod.SidecarClient, "post_json", _post_json)

    fragment = await SocialAnalyzerEnricher().run(EnrichmentRequest(username="torvalds", requested_tiers=["tier2"]))
    platforms = {h["platform"] for h in fragment["handles"]}
    assert platforms == {"GitHub", "Twitter"}
    assert len(fragment["handles"]) == 2


@pytest.mark.asyncio
async def test_fake_gmaps_contract() -> None:
    app = _load_app("google-maps-scraper")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/jobs",
            json={"name": "probe", "keywords": ["coffee"], "depth": 1, "lang": "en"},
        )
        job_id = created.json()["id"]
        status = await client.get(f"/api/v1/jobs/{job_id}")
        csv_text = await client.get(f"/api/v1/jobs/{job_id}/download")

    assert created.status_code == 200
    assert status.json()["status"] == "ok"
    assert "Hey Neighbor Cafe" in csv_text.text


@pytest.mark.asyncio
async def test_fake_gmaps_enricher_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _load_app("google-maps-scraper")
    transport = httpx.ASGITransport(app=app)
    base = "http://test"

    from app.clients import sidecar as sidecar_mod

    async def _post_json(self, path="", json=None):
        async with httpx.AsyncClient(transport=transport, base_url=base) as client:
            response = await client.post(path, json=json)
            response.raise_for_status()
            return response.json()

    async def _get_json(self, path="", params=None):
        async with httpx.AsyncClient(transport=transport, base_url=base) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def _get_text(self, path=""):
        async with httpx.AsyncClient(transport=transport, base_url=base) as client:
            response = await client.get(path)
            response.raise_for_status()
            return response.text

    monkeypatch.setattr(get_settings(), "gmaps_scraper_url", base)
    monkeypatch.setattr(get_settings(), "gmaps_job_timeout_seconds", 30)
    monkeypatch.setattr(get_settings(), "gmaps_job_poll_seconds", 0)
    monkeypatch.setattr(sidecar_mod.SidecarClient, "post_json", _post_json)
    monkeypatch.setattr(sidecar_mod.SidecarClient, "get_json", _get_json)
    monkeypatch.setattr(sidecar_mod.SidecarClient, "get_text", _get_text)

    fragment = await LocalBusinessEnricher().run(
        EnrichmentRequest(business="coffee shop San Francisco", requested_tiers=["tier4"])
    )
    business = fragment["business"]
    assert business["name"] == "Hey Neighbor Cafe"
    assert business["rating"] == pytest.approx(4.5)


@pytest.mark.asyncio
async def test_fake_reacher_contract() -> None:
    app = _load_app("reacher")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/check_email", json={"to_email": "user@example.com"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_reachable"] == "safe"
    assert payload["misc"]["is_catch_all"] is False
    assert payload["smtp"]["is_catch_all"] is False


@pytest.mark.asyncio
async def test_fake_reacher_catchall_contract() -> None:
    app = _load_app("reacher")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/check_email",
            json={"to_email": "guess@catchall.example.com"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["misc"]["is_catch_all"] is True
    assert payload["smtp"]["is_catch_all"] is True


@pytest.mark.asyncio
async def test_fake_reacher_enricher_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _load_app("reacher")
    transport = httpx.ASGITransport(app=app)
    base = "http://test"

    from app.clients import sidecar as sidecar_mod

    async def _post_json(self, path="", json=None):
        async with httpx.AsyncClient(transport=transport, base_url=base) as client:
            response = await client.post(path, json=json)
            response.raise_for_status()
            return response.json()

    async def _aftership_should_not_run(self, url: str, email: str):
        raise AssertionError("AfterShip must not run when fake Reacher is conclusive")

    monkeypatch.setattr(get_settings(), "email_verify_level", "smtp")
    monkeypatch.setattr(get_settings(), "reacher_url", base)
    monkeypatch.setattr(sidecar_mod.SidecarClient, "post_json", _post_json)
    monkeypatch.setattr(EmailVerifier, "_aftership", _aftership_should_not_run)

    result = await EmailVerifier().verify("user@example.com")
    assert result is not None
    assert result["source"] == "Reacher"
    assert result["status"] == "verified"


@pytest.mark.asyncio
async def test_fake_reacher_catchall_enricher_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _load_app("reacher")
    transport = httpx.ASGITransport(app=app)
    base = "http://test"

    from app.clients import sidecar as sidecar_mod

    async def _post_json(self, path="", json=None):
        async with httpx.AsyncClient(transport=transport, base_url=base) as client:
            response = await client.post(path, json=json)
            response.raise_for_status()
            return response.json()

    async def _aftership_should_not_run(self, url: str, email: str):
        raise AssertionError("AfterShip must not run when Reacher reports catch-all")

    monkeypatch.setattr(get_settings(), "email_verify_level", "smtp")
    monkeypatch.setattr(get_settings(), "reacher_url", base)
    monkeypatch.setattr(sidecar_mod.SidecarClient, "post_json", _post_json)
    monkeypatch.setattr(EmailVerifier, "_aftership", _aftership_should_not_run)

    result = await EmailVerifier().verify("guess@catchall.example.com")
    assert result is not None
    assert result["source"] == "Reacher"
    assert result["status"] == "catch_all"
    assert result["confidence"] < 0.5


@pytest.mark.asyncio
async def test_fake_email_verifier_contract() -> None:
    app = _load_app("email-verifier")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/user@example.com/verification")

    assert response.status_code == 200
    payload = response.json()
    assert payload["syntax"]["valid"] is True
    assert payload["reachable"] == "yes"


@pytest.mark.asyncio
async def test_fake_email_verifier_enricher_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _load_app("email-verifier")
    transport = httpx.ASGITransport(app=app)
    base = "http://test"

    from app.clients import sidecar as sidecar_mod

    async def _get_json(self, path="", params=None):
        async with httpx.AsyncClient(transport=transport, base_url=base) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    monkeypatch.setattr(get_settings(), "email_verify_level", "basic")
    monkeypatch.setattr(get_settings(), "email_verifier_url", base)
    monkeypatch.setattr(sidecar_mod.SidecarClient, "get_json", _get_json)

    result = await EmailVerifier().verify("user@example.com")
    assert result is not None
    assert result["source"] == "AfterShip Email Verifier"
    assert result["status"] == "deliverable"
