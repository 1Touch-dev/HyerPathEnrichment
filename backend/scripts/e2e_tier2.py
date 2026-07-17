"""Strict Tier 2 E2E: Sherlock / Maigret / Social Analyzer + confidence bands.

Unlike unit tests (mocked), this hits live CLIs and the social-analyzer sidecar.
Fails when any Tier 2 source returns empty while its backend is present.

Usage (typically via scripts/e2e_tier2.sh inside the api container):
  cd backend
  python scripts/e2e_tier2.py
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx

_env_root = os.environ.get("E2E_BACKEND_ROOT")
ROOT = Path(_env_root) if _env_root else Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.core.config import get_settings
from app.enrichers.maigret import MaigretEnricher
from app.enrichers.sherlock import SherlockEnricher
from app.enrichers.social_analyzer import SocialAnalyzerEnricher, extract_social_analyzer_candidates
from app.domain.enrichment import EnrichmentRequest
from app.domain.dossier import SocialHandle
from app.providers import SidecarClient
from app.enrichers.pipeline import Pipeline

RESULTS_DIR = ROOT / ".e2e-results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

USERNAME = os.getenv("E2E_TIER2_USERNAME", "torvalds")
REQUIRED_SOURCES = {"Sherlock", "Maigret", "Social Analyzer"}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    data: dict[str, Any] = field(default_factory=dict)


class Tier2Probe:
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
        print("== Tier 2 E2E probe (Stage A) ==")
        await self.check_api_health()
        self.check_clis()
        await self.check_social_analyzer_contract()
        await self.check_enrichers_live()
        await self.check_api_sync()
        await self.check_api_async()
        if os.getenv("E2E_TIER2_LLM", "").strip().lower() in {"1", "true", "yes"}:
            print("\n== Tier 2 E2E probe (Stage B litellm) ==")
            await self.check_litellm_disambiguation()

        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "username": USERNAME,
            "checks": [
                {"name": r.name, "ok": r.ok, "detail": r.detail, "data": r.data} for r in self.results
            ],
            "passed": sum(1 for r in self.results if r.ok),
            "failed": sum(1 for r in self.results if not r.ok),
        }
        report_path = RESULTS_DIR / "tier2-report.json"
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

    def check_clis(self) -> None:
        sherlock = shutil.which("sherlock")
        maigret = shutil.which("maigret")
        self.record("cli_sherlock", bool(sherlock), sherlock or "sherlock not on PATH")
        self.record("cli_maigret", bool(maigret), maigret or "maigret not on PATH")

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
                "string": USERNAME,
                "uuid": uuid.uuid4().hex,
                "option": ["FindUserProfilesFast"],
                "output": "json",
                "filter": ["all"],
                "profiles": ["detected"],
            },
        )
        (RESULTS_DIR / "tier2-social-analyzer-analyze.json").write_text(
            json.dumps(analyze, indent=2) if analyze is not None else "null",
            encoding="utf-8",
        )
        detected: list[Any] = []
        if isinstance(analyze, dict):
            detected = extract_social_analyzer_candidates(analyze)
        self.record(
            "social_analyzer_contract_analyze",
            isinstance(analyze, dict) and bool(detected),
            f"POST /analyze_string detected={len(detected) if isinstance(detected, list) else 0}",
            sample=(detected[:3] if isinstance(detected, list) else []),
        )

    async def check_enrichers_live(self) -> None:
        request = EnrichmentRequest(username=USERNAME, requested_tiers=["tier2"])

        sherlock = await SherlockEnricher().run(request)
        sherlock_ok = bool(sherlock.get("handles"))
        sherlock_conf = [h.get("confidence") for h in sherlock.get("handles", [])]
        self.record(
            "enricher_sherlock",
            sherlock_ok and all(abs(float(c) - 0.75) < 0.001 for c in sherlock_conf),
            f"handles={len(sherlock.get('handles', []))} confidences={sherlock_conf[:5]}",
        )

        maigret = await MaigretEnricher().run(request)
        maigret_ok = bool(maigret.get("handles"))
        maigret_conf = [h.get("confidence") for h in maigret.get("handles", [])]
        self.record(
            "enricher_maigret",
            maigret_ok and all(abs(float(c) - 0.85) < 0.001 for c in maigret_conf),
            f"handles={len(maigret.get('handles', []))} confidences={maigret_conf[:5]}",
        )

        if not self.settings.social_analyzer_url.strip():
            self.record("enricher_social_analyzer", False, "SOCIAL_ANALYZER_URL unset")
            return
        social = await SocialAnalyzerEnricher().run(request)
        sa_handles = social.get("handles") or []
        sa_ok = bool(sa_handles) and all(0 < float(h.get("confidence", 0)) <= 1 for h in sa_handles)
        self.record(
            "enricher_social_analyzer",
            sa_ok,
            f"handles={len(sa_handles)}",
        )

    async def check_api_sync(self) -> None:
        body = {"username": USERNAME, "requested_tiers": ["tier2"]}
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(
                    f"{self.base_url}/enrich/sync", headers=self.headers, json=body
                )
            payload = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            self.record("api_sync_tier2", False, str(exc))
            return

        (RESULTS_DIR / "tier2-sync.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        dossier = payload.get("dossier") or {}
        sources = set(dossier.get("sources") or [])
        handles = dossier.get("handles") or []
        providers = {
            str((h.get("metadata") or {}).get("provider") or "")
            for h in handles
            if isinstance(h, dict)
        }
        confidences = [float(h.get("confidence", 0)) for h in handles if isinstance(h, dict)]

        has_sherlock_band = any(abs(c - 0.75) < 0.001 for c in confidences) or "Sherlock" in providers
        has_maigret_band = any(abs(c - 0.85) < 0.001 for c in confidences) or "Maigret" in providers

        ok = (
            response.status_code == 200
            and payload.get("status") == "completed"
            and REQUIRED_SOURCES.issubset(sources)
            and bool(handles)
            and has_sherlock_band
            and has_maigret_band
        )
        self.record(
            "api_sync_tier2",
            ok,
            (
                f"status={payload.get('status')} sources={sorted(sources)} "
                f"handles={len(handles)} sherlock_band={has_sherlock_band} "
                f"maigret_band={has_maigret_band}"
            ),
            sources=sorted(sources),
            handle_count=len(handles),
        )

    async def check_api_async(self) -> None:
        body = {"username": USERNAME, "requested_tiers": ["tier2"]}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                enqueue = await client.post(f"{self.base_url}/enrich", headers=self.headers, json=body)
            if enqueue.status_code != 202:
                self.record("api_async_tier2", False, f"enqueue status={enqueue.status_code}")
                return
            job_id = enqueue.json()["id"]

            final: dict[str, Any] = {}
            async with httpx.AsyncClient(timeout=30.0) as client:
                for _ in range(90):
                    poll = await client.get(f"{self.base_url}/enrich/{job_id}", headers=self.headers)
                    final = poll.json()
                    if final.get("status") not in {"queued", "running"}:
                        break
                    await asyncio.sleep(2)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
            self.record("api_async_tier2", False, str(exc))
            return

        dossier = final.get("dossier") or {}
        handles = dossier.get("handles") or []
        sources = set(dossier.get("sources") or [])
        ok = final.get("status") == "completed" and bool(handles) and bool(sources & REQUIRED_SOURCES)
        self.record(
            "api_async_tier2",
            ok,
            f"status={final.get('status')} handles={len(handles)} sources={sorted(sources)}",
        )

    async def check_litellm_disambiguation(self) -> None:
        settings = get_settings()
        if settings.llm_mode != "litellm":
            self.record(
                "litellm_disambiguation",
                False,
                f"LLM_MODE={settings.llm_mode!r} (expected litellm)",
            )
            return
        if "litellm" not in settings.litellm_api_base:
            self.record(
                "litellm_disambiguation",
                False,
                f"LITELLM_API_BASE={settings.litellm_api_base!r}",
            )
            return

        orch = Pipeline(db=AsyncMock())
        request = EnrichmentRequest(
            username="jane-doe",
            email="jane.doe@acme.com",
            requested_tiers=["tier2", "tier3"],
        )
        handles = [
            SocialHandle(
                platform="X",
                username="jane_doe",
                profile_url="https://x.com/jane_doe",
                confidence=0.35,
            ),
            SocialHandle(
                platform="GitHub",
                username="totally-unrelated-bot-xyz-999",
                profile_url="https://github.com/totally-unrelated-bot-xyz-999",
                confidence=0.40,
            ),
            SocialHandle(
                platform="GitHub",
                username="jane-doe",
                profile_url="https://github.com/jane-doe",
                confidence=0.9,
            ),
        ]
        try:
            kept, dropped = await orch._disambiguate_handles(request, handles)
        except Exception as exc:
            self.record("litellm_disambiguation", False, f"compare failed: {exc}")
            return

        names = {(h.platform, h.username) for h in kept}
        ok = ("GitHub", "jane-doe") in names and ("GitHub", "totally-unrelated-bot-xyz-999") not in names
        self.record(
            "litellm_disambiguation",
            ok,
            f"kept={[(h.platform, h.username, round(h.confidence, 2)) for h in kept]} dropped={dropped}",
        )


async def _amain() -> int:
    return await Tier2Probe().run()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_amain()))
