import json
from pathlib import Path
from typing import Any

import pytest

from app.config import get_settings
from app.enrichers import gitrecon as gitrecon_mod
from app.enrichers import sherlock as sherlock_mod
from app.enrichers.base import Enricher
from app.enrichers.email_discover import EmailDiscoverEnricher
from app.enrichers.gitrecon import GitReconEnricher
from app.enrichers.jobspy import JobSpyEnricher
from app.enrichers.local_business import LocalBusinessEnricher
from app.enrichers.sherlock import SherlockEnricher
from app.enrichers.social_analyzer import SocialAnalyzerEnricher
from app.models import EnrichmentRequest
from app.providers import EmailVerifier, ProxyProvider
from app.providers import sidecar as sidecar_mod


def _cmd(returncode: int, stdout: str):
    async def _run(args, timeout, env=None):
        return returncode, stdout, ""

    return _run


async def test_gitrecon_parses_output_file(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "username": "octocat",
        "orgs": ["github"],
        "leaked_emails": ["octocat@github.com"],
    }

    async def _run(args, timeout, env=None, cwd=None):
        assert cwd
        result = Path(cwd) / "results" / "octocat" / "octocat_github.json"
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text(json.dumps(payload), encoding="utf-8")
        return 0, "", ""

    monkeypatch.setattr(gitrecon_mod, "run_command", _run)
    fragment = await GitReconEnricher().run(EnrichmentRequest(username="octocat"))
    assert fragment["handles"][0]["platform"] == "GitHub"
    assert fragment["github"]["organizations"] == ["github"]
    assert fragment["emails"] == ["octocat@github.com"]
    assert fragment["sources"] == ["GitRecon"]


async def test_gitrecon_degrades_when_tool_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gitrecon_mod, "run_command", _cmd(127, ""))
    fragment = await GitReconEnricher().run(EnrichmentRequest(username="octocat"))
    assert fragment == {}


async def test_email_discover_falls_back_to_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.enrichers import email_discover as email_discover_mod

    monkeypatch.setattr(email_discover_mod, "run_command", _cmd(127, ""))
    fragment = await EmailDiscoverEnricher().run(
        EnrichmentRequest(username="jane", company="Acme Corp")
    )
    assert fragment["emails"] == ["jane@acmecorp.com"]


async def test_email_verifier_basic_syntax_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_mx(self, domain: str):
        return None

    monkeypatch.setattr(EmailVerifier, "_mx_ok", _no_mx)
    verifier = EmailVerifier()
    assert await verifier.verify("not-an-email") is None
    result = await verifier.verify("jane@example.com")
    assert result["value"] == "jane@example.com"
    assert set(result) == {"value", "status", "confidence", "source"}


async def test_email_verifier_rejects_disposable_before_mx(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _mx_should_not_run(self, domain: str):
        raise AssertionError("MX must not run for disposable addresses")

    async def _aftership_should_not_run(self, url: str, email: str):
        raise AssertionError("AfterShip must not run for disposable addresses")

    async def _reacher_should_not_run(self, url: str, email: str):
        raise AssertionError("Reacher must not run for disposable addresses")

    monkeypatch.setattr(EmailVerifier, "_mx_ok", _mx_should_not_run)
    monkeypatch.setattr(EmailVerifier, "_aftership", _aftership_should_not_run)
    monkeypatch.setattr(EmailVerifier, "_reacher", _reacher_should_not_run)

    result = await EmailVerifier().verify("user@mailinator.com")
    assert result == {
        "value": "user@mailinator.com",
        "status": "disposable",
        "confidence": 0.0,
        "source": "mailchecker",
    }


async def test_sherlock_parses_found_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = "[+] GitHub: https://github.com/jane\n[+] Twitter: https://twitter.com/jane\n"
    monkeypatch.setattr(sherlock_mod, "run_command", _cmd(0, stdout))
    fragment = await SherlockEnricher().run(EnrichmentRequest(username="jane"))
    platforms = {handle["platform"] for handle in fragment["handles"]}
    assert platforms == {"Github", "Twitter"}


async def test_social_analyzer_maps_sidecar(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _post_json(self, path="", json=None):
        return {
            "user_info_normal": {
                "data": [
                    {"type": "GitHub", "link": "https://github.com/jane", "good": "true", "rate": 95},
                    {"type": "Twitter", "link": "https://twitter.com/jane", "good": "true", "rate": "%100.00"},
                ]
            }
        }

    monkeypatch.setattr(sidecar_mod.SidecarClient, "post_json", _post_json)
    fragment = await SocialAnalyzerEnricher().run(EnrichmentRequest(username="jane"))
    assert fragment["handles"][0]["platform"] == "GitHub"
    assert fragment["handles"][0]["confidence"] == pytest.approx(0.95)
    assert fragment["handles"][1]["platform"] == "Twitter"
    assert fragment["handles"][1]["confidence"] == pytest.approx(1.0)


async def test_local_business_empty_when_sidecar_unset() -> None:
    # No GMAPS_SCRAPER_URL by default -> sidecar disabled -> empty fragment.
    fragment = await LocalBusinessEnricher().run(EnrichmentRequest(business="Joe's Coffee"))
    assert fragment == {}


async def test_jobspy_maps_scraped_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    def _scrape(self, search_term, company, limit):
        return [{"title": "SRE", "company": "Acme", "location": "Remote", "is_remote": True, "site": "indeed"}]

    monkeypatch.setattr(JobSpyEnricher, "_scrape", _scrape)
    fragment = await JobSpyEnricher().run(EnrichmentRequest(job_search="SRE"))
    assert fragment["jobs"][0]["title"] == "SRE"
    assert fragment["jobs"][0]["remote"] is True


def test_proxy_provider_free_mode_is_direct(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "proxy_mode", "none")
    assert ProxyProvider().get() is None


def test_proxy_provider_scrapoxy_builds_authenticated_url(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "proxy_mode", "scrapoxy")
    monkeypatch.setattr(settings, "scrapoxy_url", "http://scrapoxy:8888")
    monkeypatch.setattr(settings, "scrapoxy_username", "user")
    monkeypatch.setattr(settings, "scrapoxy_password", "pass")
    assert ProxyProvider().get() == "http://user:pass@scrapoxy:8888"


async def test_base_run_degrades_on_exception() -> None:
    class Boom(Enricher):
        source_name = "Boom"

        async def validate(self, request: EnrichmentRequest) -> bool:
            return True

        async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
            raise RuntimeError("backend down")

    assert await Boom().run(EnrichmentRequest(username="x")) == {}
