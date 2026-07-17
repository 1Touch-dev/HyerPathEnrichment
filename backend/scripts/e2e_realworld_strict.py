"""Strict real-world E2E probe for enricher integrations.

Unlike unit tests (mocked) and shape tests (offline stubs), this script hits
live sidecars/tools and fails when:
  - a configured service is reachable but the contract/parser is wrong
  - an enricher returns an empty fragment while its backend is healthy

Prerequisites (typically via scripts/e2e_realworld_strict.sh in WSL):
  - Docker stack up: api, worker, redis, postgres, social-analyzer, gmaps
  - gitrecon cloned and GITRECON_SCRIPT pointing at gitrecon.py

Usage:
  cd backend
  python scripts/e2e_realworld_strict.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

# Allow running as a script from backend/ or via stdin inside Docker (E2E_BACKEND_ROOT).
_env_root = os.environ.get("E2E_BACKEND_ROOT")
ROOT = Path(_env_root) if _env_root else Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.core.config import get_settings
from app.enrichers.email_discover import EmailDiscoverEnricher
from app.enrichers.email_verify import EmailVerifyEnricher
from app.enrichers.gitrecon import GitReconEnricher
from app.enrichers.local_business import LocalBusinessEnricher
from app.enrichers.social_analyzer import SocialAnalyzerEnricher, extract_social_analyzer_candidates
from app.domain.enrichment import EnrichmentRequest
from app.clients.sidecar import SidecarClient

RESULTS_DIR = ROOT / ".e2e-results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    data: dict[str, Any] = field(default_factory=dict)


class StrictProbe:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = os.getenv("E2E_BASE_URL", "http://localhost:8000").rstrip("/")
        self.token = self.settings.api_token
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.results: list[CheckResult] = []

    def record(self, name: str, ok: bool, detail: str, **data: Any) -> None:
        result = CheckResult(name=name, ok=ok, detail=detail, data=data)
        self.results.append(result)
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {name}: {detail}")

    async def run(self) -> int:
        print("== strict real-world E2E probe ==")
        await self.check_api_health()
        await self.check_gmaps_contract()
        await self.check_social_analyzer_contract()
        await self.check_enrichers_live()
        await self.check_api_sync_paths()

        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "checks": [
                {"name": r.name, "ok": r.ok, "detail": r.detail, "data": r.data} for r in self.results
            ],
            "passed": sum(1 for r in self.results if r.ok),
            "failed": sum(1 for r in self.results if not r.ok),
        }
        report_path = RESULTS_DIR / "strict-report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nReport written to {report_path}")
        print(f"Summary: {report['passed']} passed, {report['failed']} failed")
        return 0 if report["failed"] == 0 else 1

    async def check_api_health(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/health")
            self.record(
                "api_health",
                response.status_code == 200 and response.json().get("status") == "ok",
                f"status={response.status_code}",
            )
        except httpx.HTTPError as exc:
            self.record("api_health", False, str(exc))

    async def check_gmaps_contract(self) -> None:
        url = self.settings.gmaps_scraper_url.strip()
        if not url:
            self.record("gmaps_configured", False, "GMAPS_SCRAPER_URL unset")
            return
        client = SidecarClient(url, timeout=60.0)

        created = await client.post_json(
            "/api/v1/jobs",
            json={
                "name": "e2e-probe",
                "keywords": ["coffee shop San Francisco"],
                "depth": 1,
                "lang": "en",
                "max_time": 180_000_000_000,
            },
        )
        (RESULTS_DIR / "gmaps-create.json").write_text(json.dumps(created, indent=2), encoding="utf-8")
        ok_create = isinstance(created, dict) and "id" in created
        self.record(
            "gmaps_contract_create",
            ok_create,
            "POST /api/v1/jobs returned id" if ok_create else f"unexpected create payload: {created}",
            payload=created,
        )
        if not ok_create:
            return

        job_id = str(created["id"])
        deadline = time.monotonic() + self.settings.gmaps_job_timeout_seconds
        terminal_state = ""
        status_payload: dict[str, Any] = {}
        while time.monotonic() < deadline:
            status_payload = await client.get_json(f"/api/v1/jobs/{job_id}") or {}
            terminal_state = str(status_payload.get("Status", status_payload.get("status", ""))).lower()
            if terminal_state in {"ok", "completed", "done"}:
                break
            if terminal_state in {"failed", "error"}:
                break
            await asyncio.sleep(self.settings.gmaps_job_poll_seconds)

        (RESULTS_DIR / "gmaps-job-status.json").write_text(
            json.dumps(status_payload, indent=2), encoding="utf-8"
        )
        ok_terminal = terminal_state in {"ok", "completed", "done"}
        self.record(
            "gmaps_contract_poll",
            ok_terminal,
            f"terminal status={terminal_state or 'timeout'}",
            job_id=job_id,
        )

        csv_text = await client.get_text(f"/api/v1/jobs/{job_id}/download") if ok_terminal else None
        has_rows = bool(csv_text and csv_text.strip() and "\n" in csv_text)
        self.record(
            "gmaps_contract_download",
            has_rows,
            f"csv_bytes={len(csv_text or '')}",
        )

        # Legacy GET /search exists on some builds but LocalBusinessEnricher uses the job API.
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                legacy = await http.get(f"{url.rstrip('/')}/search", params={"q": "coffee", "depth": 1})
            self.record(
                "gmaps_legacy_search_unused",
                legacy.status_code == 200,
                f"GET /search status={legacy.status_code} (legacy; enricher uses POST /api/v1/jobs)",
            )
        except httpx.HTTPError as exc:
            self.record("gmaps_legacy_search_unused", True, f"GET /search unreachable: {exc}")

    async def check_social_analyzer_contract(self) -> None:
        url = self.settings.social_analyzer_url.strip()
        if not url:
            self.record("social_analyzer_configured", False, "SOCIAL_ANALYZER_URL unset")
            return

        client = SidecarClient(url, timeout=180.0)
        settings_payload = await client.get_json("/get_settings")
        self.record(
            "social_analyzer_contract_settings",
            isinstance(settings_payload, dict) and "websites" in settings_payload,
            "GET /get_settings returned websites list"
            if isinstance(settings_payload, dict)
            else f"unexpected settings: {settings_payload}",
        )

        analyze = await client.post_json(
            "/analyze_string",
            json={
                "string": "torvalds",
                "uuid": uuid.uuid4().hex,
                "option": ["FindUserProfilesFast"],
                "output": "json",
                "filter": ["all"],
                "profiles": ["detected"],
            },
        )
        (RESULTS_DIR / "social-analyzer-analyze.json").write_text(
            json.dumps(analyze, indent=2) if analyze is not None else "null",
            encoding="utf-8",
        )
        detected: list[Any] = []
        if isinstance(analyze, dict):
            detected = extract_social_analyzer_candidates(analyze)
        self.record(
            "social_analyzer_contract_analyze",
            isinstance(analyze, dict) and bool(detected),
            f"POST /analyze_string detected={len(detected)}",
            sample=detected[:3] if detected else [],
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                legacy = await http.get(f"{url.rstrip('/')}/search", params={"username": "torvalds"})
            # Legacy route may 200 or 404 depending on SA build; enricher does not use it.
            self.record(
                "social_analyzer_legacy_search_unused",
                legacy.status_code in {200, 404},
                f"GET /search status={legacy.status_code} (legacy; enricher uses POST /analyze_string)",
            )
        except httpx.HTTPError as exc:
            self.record("social_analyzer_legacy_search_unused", True, f"GET /search unreachable: {exc}")

    async def check_enrichers_live(self) -> None:
        discover = await EmailDiscoverEnricher().run(
            EnrichmentRequest(
                username="jane",
                company="Example Corp",
                requested_tiers=["tier3"],
            )
        )
        self.record(
            "enricher_email_discover",
            bool(discover.get("emails")),
            f"emails={discover.get('emails', [])}",
        )

        verify = await EmailVerifyEnricher().run(
            EnrichmentRequest(email="jane.doe@example.com", requested_tiers=["tier3"])
        )
        self.record(
            "enricher_email_verify",
            bool(verify.get("verified_emails")),
            f"verified={len(verify.get('verified_emails', []))}",
        )

        if self.settings.gitrecon_script.strip() or os.getenv("GITRECON_SCRIPT"):
            gitrecon = await GitReconEnricher().run(
                EnrichmentRequest(username="torvalds", requested_tiers=["tier3"])
            )
            self.record(
                "enricher_gitrecon",
                bool(gitrecon.get("handles")),
                f"handles={len(gitrecon.get('handles', []))} github_orgs={len(gitrecon.get('github', {}).get('organizations', []))}",
            )
        else:
            self.record("enricher_gitrecon", False, "GITRECON_SCRIPT unset — install gitrecon for strict run")

        if self.settings.social_analyzer_url.strip():
            social = await SocialAnalyzerEnricher().run(
                EnrichmentRequest(username="torvalds", requested_tiers=["tier2"])
            )
            self.record(
                "enricher_social_analyzer",
                bool(social.get("handles")),
                f"handles={len(social.get('handles', []))}",
            )

        if self.settings.gmaps_scraper_url.strip():
            business = await LocalBusinessEnricher().run(
                EnrichmentRequest(
                    business="coffee shop San Francisco",
                    requested_tiers=["tier4"],
                )
            )
            self.record(
                "enricher_local_business",
                business.get("business") is not None,
                f"business_name={business.get('business', {}).get('name') if business else None}",
            )

    async def check_api_sync_paths(self) -> None:
        body = {
            "username": "torvalds",
            "email": "torvalds@example.com",
            "company": "Linux",
            "business": "coffee shop San Francisco",
            "requested_tiers": ["tier2", "tier3", "tier4"],
        }
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/enrich/sync",
                    headers={**self.headers, "Content-Type": "application/json"},
                    json=body,
                )
            payload = response.json()
            (RESULTS_DIR / "api-sync-dossier.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
            dossier = payload.get("dossier", {})
            self.record(
                "api_sync_completed",
                response.status_code == 200 and payload.get("status") == "completed",
                f"status={payload.get('status')}",
            )
            self.record(
                "api_sync_has_handles_or_emails",
                bool(dossier.get("handles") or dossier.get("emails") or dossier.get("verified_emails")),
                f"handles={len(dossier.get('handles', []))} emails={len(dossier.get('emails', []))}",
            )
            self.record(
                "api_sync_business_optional",
                dossier.get("business") is not None or not self.settings.gmaps_scraper_url.strip(),
                f"business={'yes' if dossier.get('business') else 'no'}",
            )
        except httpx.HTTPError as exc:
            self.record("api_sync_completed", False, str(exc))


def main() -> int:
    return asyncio.run(StrictProbe().run())


if __name__ == "__main__":
    raise SystemExit(main())
