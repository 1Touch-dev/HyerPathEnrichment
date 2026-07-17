"""CI-safe fake sidecar E2E: HTTP reachability, enricher integration, async tier4 path.

Usage (typically via scripts/e2e_fake_sidecars.sh):
  cd backend
  python scripts/e2e_fake_sidecars.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

_env_root = os.environ.get("E2E_BACKEND_ROOT")
ROOT = Path(_env_root) if _env_root else Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.core.config import get_settings
from app.enrichers.local_business import LocalBusinessEnricher
from app.enrichers.social_analyzer import SocialAnalyzerEnricher
from app.enrichers.email_verify import EmailVerifyEnricher
from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import RequestedTier
from app.providers import EmailVerifier, SidecarClient

RESULTS_DIR = ROOT / ".e2e-results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_BUSINESS_NAME = "Hey Neighbor Cafe"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    data: dict[str, Any] = field(default_factory=dict)


class FakeSidecarProbe:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = os.getenv("E2E_BASE_URL", "http://localhost:8000").rstrip("/")
        self.token = self.settings.api_token
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.results: list[CheckResult] = []

    def record(self, name: str, ok: bool, detail: str, **data: Any) -> None:
        result = CheckResult(name=name, ok=ok, detail=detail, data=data)
        self.results.append(result)
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    async def run(self) -> int:
        print("== Fake sidecar E2E probe ==")
        await self.check_api_health()
        await self.check_sidecar_health()
        await self.check_enrichers()
        await self.check_api_async_tier4()

        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "checks": [
                {"name": r.name, "ok": r.ok, "detail": r.detail, "data": r.data} for r in self.results
            ],
            "passed": sum(1 for r in self.results if r.ok),
            "failed": sum(1 for r in self.results if not r.ok),
        }
        report_path = RESULTS_DIR / "fake-sidecars-report.json"
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

    async def check_sidecar_health(self) -> None:
        checks = [
            (
                "fake_sa_health",
                self.settings.social_analyzer_url,
                "GET",
                "/get_settings",
                lambda payload: isinstance(payload, dict) and "websites" in payload,
            ),
            (
                "fake_gmaps_health",
                self.settings.gmaps_scraper_url,
                "POST",
                "/api/v1/jobs",
                lambda payload: isinstance(payload, dict) and "id" in payload,
            ),
            (
                "fake_email_verifier_health",
                self.settings.email_verifier_url,
                "GET",
                "/v1/health@example.com/verification",
                lambda payload: isinstance(payload, dict) and payload.get("syntax", {}).get("valid") is True,
            ),
            (
                "fake_reacher_health",
                self.settings.reacher_url,
                "POST",
                "/v1/check_email",
                lambda payload: isinstance(payload, dict) and payload.get("is_reachable") == "safe",
            ),
        ]

        for name, base_url, method, path, predicate in checks:
            url = (base_url or "").strip()
            if not url:
                self.record(name, False, "URL unset")
                continue
            client = SidecarClient(url, timeout=30.0)
            if method == "GET":
                payload = await client.get_json(path)
            else:
                payload = await client.post_json(path, json={"to_email": "user@example.com"})
            self.record(name, predicate(payload), f"{method} {path}")

    async def check_enrichers(self) -> None:
        social = await SocialAnalyzerEnricher().run(
            EnrichmentRequest(username="torvalds", requested_tiers=[RequestedTier.tier2])
        )
        sa_handles = social.get("handles") or []
        sa_platforms = {h.get("platform") for h in sa_handles}
        self.record(
            "enricher_social_analyzer",
            sa_platforms == {"GitHub", "Twitter"} and len(sa_handles) == 2,
            f"handles={len(sa_handles)} platforms={sorted(sa_platforms)}",
        )

        business = await LocalBusinessEnricher().run(
            EnrichmentRequest(
                business="coffee shop San Francisco",
                requested_tiers=[RequestedTier.tier4],
            )
        )
        biz = business.get("business") or {}
        self.record(
            "enricher_local_business",
            biz.get("name") == EXPECTED_BUSINESS_NAME,
            f"business_name={biz.get('name')}",
        )

        from unittest.mock import patch

        basic_settings = get_settings().model_copy(update={"email_verify_level": "basic"})
        with patch("app.providers.email_verify.get_settings", return_value=basic_settings):
            basic = await EmailVerifier().verify("user@example.com")
        self.record(
            "enricher_email_verify_basic",
            basic is not None and basic.get("source") == "AfterShip Email Verifier",
            f"source={basic.get('source') if basic else None}",
        )

        smtp = await EmailVerifyEnricher().run(
            EnrichmentRequest(email="user@example.com", requested_tiers=[RequestedTier.tier3])
        )
        verified = smtp.get("verified_emails") or []
        reacher_hits = [v for v in verified if v.get("source") == "Reacher"]
        self.record(
            "enricher_email_verify_smtp",
            bool(reacher_hits) and reacher_hits[0].get("status") == "verified",
            f"reacher_hits={len(reacher_hits)}",
        )

    async def check_api_async_tier4(self) -> None:
        body = {
            "business": "coffee shop San Francisco",
            "requested_tiers": ["tier4"],
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                enqueue = await client.post(
                    f"{self.base_url}/enrich", headers=self.headers, json=body
                )
            if enqueue.status_code != 202:
                self.record("api_async_tier4", False, f"enqueue status={enqueue.status_code}")
                return
            job_id = enqueue.json().get("id")
            final = ""
            dossier: dict[str, Any] = {}
            for _ in range(40):
                async with httpx.AsyncClient(timeout=30.0) as client:
                    poll = await client.get(f"{self.base_url}/enrich/{job_id}", headers=self.headers)
                payload = poll.json()
                final = payload.get("status", "")
                dossier = payload.get("dossier") or {}
                if final not in {"queued", "running"}:
                    break
                await asyncio.sleep(2)

            sources = set(dossier.get("sources") or [])
            business = dossier.get("business") or {}
            ok = (
                final == "completed"
                and "Google Maps Scraper" in sources
                and business.get("name") == EXPECTED_BUSINESS_NAME
            )
            self.record(
                "api_async_tier4",
                ok,
                f"status={final} sources={sorted(sources)} business={business.get('name')}",
            )
        except httpx.HTTPError as exc:
            self.record("api_async_tier4", False, str(exc))


def main() -> int:
    return asyncio.run(FakeSidecarProbe().run())


if __name__ == "__main__":
    raise SystemExit(main())
