import json
from pathlib import Path
from typing import Any

import pytest

from app.config import get_settings
from app.enrichers import gitrecon as gitrecon_mod
from app.enrichers import sherlock as sherlock_mod
from app.enrichers.base import Enricher
from app.enrichers.email_discover import EmailDiscoverEnricher
from app.enrichers.email_verify import EmailVerifyEnricher
from app.enrichers.crosslinked import CrossLinkedEnricher
from app.enrichers.gitrecon import GitReconEnricher, fragment_from_gitrecon_data
from app.enrichers.jobspy import JobSpyEnricher
from app.enrichers.local_business import LocalBusinessEnricher
from app.enrichers.sherlock import SherlockEnricher
from app.enrichers.social_analyzer import SocialAnalyzerEnricher, extract_social_analyzer_candidates
from app.models import EnrichmentRequest
from app.providers import EmailVerifier, ProxyProvider
from app.providers import sidecar as sidecar_mod


def _cmd(returncode: int, stdout: str):
    async def _run(args, timeout, env=None):
        return returncode, stdout, ""

    return _run


async def test_gitrecon_parses_output_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "gitrecon_script", "")
    payload = {
        "username": "octocat",
        "orgs": ["github"],
        "leaked_emails": ["octocat@github.com"],
    }

    async def _run(args, timeout, env=None, cwd=None):
        assert cwd
        assert args == ["python3", "gitrecon.py", "octocat", "-s", "github", "-o"]
        assert (Path(cwd) / "results").is_dir()
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


async def test_crosslinked_reads_names_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from app.enrichers import crosslinked as crosslinked_mod

    names_file = tmp_path / "crosslinked_names.txt"
    names_file.write_text("jane.doe@microsoft.com\njohn.smith@microsoft.com\n", encoding="utf-8")

    async def _run(args, timeout, env=None, cwd=None):
        assert "--search" in args
        target = Path(cwd) / "crosslinked_names.txt"
        target.write_text(names_file.read_text(encoding="utf-8"), encoding="utf-8")
        return 0, "", ""

    monkeypatch.setattr(get_settings(), "crosslinked_search_engines", "yahoo")
    monkeypatch.setattr(crosslinked_mod, "run_command", _run)
    fragment = await CrossLinkedEnricher().run(EnrichmentRequest(company="Microsoft"))
    assert fragment["coworkers"] == ["Jane Doe", "John Smith"]
    assert "jane.doe@microsoft.com" in fragment["emails"]
    assert fragment["sources"] == ["CrossLinked"]


async def test_email_discover_falls_back_to_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.enrichers import email_discover as email_discover_mod

    monkeypatch.setattr(email_discover_mod, "run_command", _cmd(127, ""))
    fragment = await EmailDiscoverEnricher().run(
        EnrichmentRequest(username="jane", company="Acme Corp")
    )
    assert fragment["emails"] == ["jane@acmecorp.com"]


async def test_email_discover_parses_sleuth_json(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.enrichers import email_discover as email_discover_mod

    stdout = json.dumps([{"email": "jane.doe@acme.com"}, {"email": "jdoe@acme.com"}])
    monkeypatch.setattr(email_discover_mod, "run_command", _cmd(0, stdout))
    fragment = await EmailDiscoverEnricher().run(
        EnrichmentRequest(username="jane", company="Acme Corp")
    )
    assert fragment["emails"] == ["jane.doe@acme.com", "jdoe@acme.com"]


async def test_gitrecon_fixture_torvalds() -> None:
    fixture = Path(__file__).parent / "fixtures" / "gitrecon_torvalds_github.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    fragment = fragment_from_gitrecon_data(data, username="torvalds")
    assert fragment["handles"][0]["username"] == "torvalds"
    assert fragment["github"]["organizations"] == ["torvalds", "linux"]
    assert fragment["github"]["public_commits"] == 42
    assert fragment["emails"] == ["torvalds@linux-foundation.org"]


async def test_email_verify_batch_returns_sources() -> None:
    async def _verify(email: str):
        return {
            "value": email,
            "status": "deliverable",
            "confidence": 0.55,
            "source": "mx",
        }

    enricher = EmailVerifyEnricher()
    enricher.verifier.verify = _verify  # type: ignore[method-assign]
    fragment = await enricher.verify_emails(["a@example.com"])
    assert fragment["sources"] == ["Email Verify"]
    assert len(fragment["verified_emails"]) == 1


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
    assert all(handle["confidence"] == pytest.approx(0.75) for handle in fragment["handles"])
    assert fragment["sources"] == ["Sherlock"]


async def test_maigret_parses_found_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.enrichers import maigret as maigret_mod
    from app.enrichers.maigret import MaigretEnricher

    stdout = "[+] GitHub: https://github.com/jane\n"
    monkeypatch.setattr(maigret_mod, "run_command", _cmd(0, stdout))
    fragment = await MaigretEnricher().run(EnrichmentRequest(username="jane"))
    assert fragment["handles"][0]["confidence"] == pytest.approx(0.85)
    assert fragment["handles"][0]["metadata"]["provider"] == "Maigret"
    assert fragment["sources"] == ["Maigret"]


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


async def test_social_analyzer_maps_fixture_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = Path(__file__).parent / "fixtures" / "social_analyzer_analyze_string.json"
    sample = json.loads(fixture.read_text(encoding="utf-8"))

    async def _post_json(self, path="", json=None):
        return sample

    monkeypatch.setattr(sidecar_mod.SidecarClient, "post_json", _post_json)
    fragment = await SocialAnalyzerEnricher().run(EnrichmentRequest(username="torvalds"))
    assert len(fragment["handles"]) == 2
    by_platform = {h["platform"]: h for h in fragment["handles"]}
    assert by_platform["GitHub"]["confidence"] == pytest.approx(0.95)
    assert by_platform["Twitter"]["confidence"] == pytest.approx(0.8)
    assert "Reddit" not in by_platform  # good=false filtered


async def test_local_business_empty_when_sidecar_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Sidecar disabled when URL unset -> empty fragment (ignore host .env).
    monkeypatch.setattr(get_settings(), "gmaps_scraper_url", "")
    fragment = await LocalBusinessEnricher().run(EnrichmentRequest(business="Joe's Coffee"))
    assert fragment == {}


async def test_local_business_maps_job_and_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "gmaps_scraper_url", "http://gmaps:8080")
    monkeypatch.setattr(get_settings(), "gmaps_job_timeout_seconds", 30)
    monkeypatch.setattr(get_settings(), "gmaps_job_poll_seconds", 0)

    csv_body = (
        "title,address,website,review_rating,phone\n"
        "Hey Neighbor Cafe,123 Main St,https://example.com,4.5,+1-555-0100\n"
    )

    async def _post_json(self, path="", json=None):
        assert path == "/api/v1/jobs"
        return {"id": "job-abc"}

    async def _get_json(self, path="", params=None):
        assert path == "/api/v1/jobs/job-abc"
        return {"status": "ok"}

    async def _get_text(self, path=""):
        assert path == "/api/v1/jobs/job-abc/download"
        return csv_body

    monkeypatch.setattr(sidecar_mod.SidecarClient, "post_json", _post_json)
    monkeypatch.setattr(sidecar_mod.SidecarClient, "get_json", _get_json)
    monkeypatch.setattr(sidecar_mod.SidecarClient, "get_text", _get_text)

    fragment = await LocalBusinessEnricher().run(
        EnrichmentRequest(business="coffee shop San Francisco")
    )
    business = fragment["business"]
    assert business["name"] == "Hey Neighbor Cafe"
    assert business["address"] == "123 Main St"
    assert business["website"] == "https://example.com"
    assert business["rating"] == pytest.approx(4.5)
    assert business["phone"] == "+1-555-0100"
    assert business["metadata"]["job_id"] == "job-abc"


def test_extract_social_analyzer_candidates_fallback() -> None:
    fixture = Path(__file__).parent / "fixtures" / "social_analyzer_analyze_string.json"
    sample = json.loads(fixture.read_text(encoding="utf-8"))
    candidates = extract_social_analyzer_candidates(sample)
    assert len(candidates) == 3

    fallback = extract_social_analyzer_candidates({"detected": [{"type": "GitHub", "link": "https://github.com/x"}]})
    assert len(fallback) == 1


def test_local_business_parses_gmaps_fixture_csv() -> None:
    csv_text = (Path(__file__).parent / "fixtures" / "gmaps_sample_row.csv").read_text(encoding="utf-8")
    row = LocalBusinessEnricher()._first_csv_row(csv_text)
    assert row is not None
    assert row["title"] == "Hey Neighbor Cafe"
    assert row["review_rating"] == "4.5"


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
