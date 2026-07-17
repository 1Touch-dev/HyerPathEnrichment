"""Run a Tier 1 canary set through the real API + worker path.

Unlike ``probe_tier1_canary.py`` (isolation scrape), this script:

  POST /enrich  ->  poll GET /enrich/{id}  ->  PASS / FAIL / SKIP

Usage:
  cd backend
  python scripts/e2e_tier1_canary.py --file docs/tier1_canary_set.json
  python scripts/e2e_tier1_canary.py --file docs/tier1_canary_set.example.json --limit 3 --json

Requires a running API + Redis + RQ worker with ENABLE_TIER1=true and Multilogin
on the host. Live LinkedIn only — not for CI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.integrations.linkedin.browser_facade import extract_linkedin_slug

RESULTS_DIR = ROOT / ".e2e-results"
SOURCE_NAME = "linkedin-photo"
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_POLL_TIMEOUT = 300.0
DEFAULT_POLL_INTERVAL = 5.0


@dataclass
class CanaryProfile:
    slug: str
    linkedin_url: str
    category: str
    expect_photo: bool


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProfileResult:
    slug: str
    linkedin_url: str
    category: str
    expect_photo: bool
    status: str  # PASS | FAIL | SKIP
    detail: str
    job_id: str | None = None
    job_status: str | None = None
    asset_url: str | None = None
    sources: list[str] = field(default_factory=list)


def default_expect_photo(category: str, explicit: bool | None = None) -> bool:
    """Resolve expect_photo: explicit flag wins; else private → False, others → True."""
    if explicit is not None:
        return explicit
    return str(category or "").strip().lower() != "private"


def load_canary_entries(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("canary file must be a JSON array")
    return raw


def parse_canary_profile(entry: dict[str, Any]) -> tuple[CanaryProfile | None, str]:
    """Return (profile, skip_reason). profile is None when the row should SKIP."""
    url = str(entry.get("linkedin_url") or "").strip()
    slug = extract_linkedin_slug(url) or str(entry.get("slug") or "").strip().lower()
    category = str(entry.get("category") or "unknown")
    if not url or not slug:
        return None, "missing linkedin_url or slug"

    explicit: bool | None
    if "expect_photo" in entry:
        explicit = bool(entry["expect_photo"])
    else:
        explicit = None

    return (
        CanaryProfile(
            slug=slug,
            linkedin_url=url,
            category=category,
            expect_photo=default_expect_photo(category, explicit),
        ),
        "",
    )


def score_job_payload(job: dict[str, Any], *, expect_photo: bool) -> tuple[str, str]:
    """Score a GET /enrich/{id} JSON body. Returns (PASS|FAIL, detail)."""
    status = str(job.get("status") or "")
    if status in {"queued", "running"}:
        return "FAIL", f"timeout waiting for job (last status={status})"
    if status == "failed":
        return "FAIL", "job status=failed"
    if status != "completed":
        return "FAIL", f"unexpected job status={status!r}"

    dossier = job.get("dossier") or {}
    photo = dossier.get("photo") or {}
    asset_url = str(photo.get("asset_url") or "").strip()
    sources = [str(s) for s in (dossier.get("sources") or [])]

    if expect_photo:
        if not asset_url:
            return "FAIL", "completed but dossier.photo.asset_url missing"
        if SOURCE_NAME not in sources:
            return "FAIL", f"completed but {SOURCE_NAME!r} not in sources={sources}"
        return "PASS", f"photo ok asset_url={asset_url[:80]}"

    return "PASS", f"completed without photo requirement sources={sources}"


def sync_guard_ok(body: dict[str, Any]) -> tuple[bool, str]:
    """Sync path must not return a Tier 1 photo."""
    dossier = body.get("dossier") or {}
    photo = dossier.get("photo")
    sources = [str(s) for s in (dossier.get("sources") or [])]
    if photo:
        return False, "sync returned dossier.photo (Tier 1 must be skipped)"
    if SOURCE_NAME in sources:
        return False, f"sync sources include {SOURCE_NAME!r}"
    return True, f"sync skipped tier1 sources={sources}"


class Tier1ApiCanary:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        poll_timeout: float = DEFAULT_POLL_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}
        self.poll_timeout = poll_timeout
        self.poll_interval = poll_interval
        self.checks: list[CheckResult] = []
        self.rows: list[ProfileResult] = []

    def record_check(self, name: str, ok: bool, detail: str, **data: Any) -> None:
        self.checks.append(CheckResult(name=name, ok=ok, detail=detail, data=data))
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    async def run(
        self,
        profiles: list[CanaryProfile],
        *,
        skip_sync_guard: bool = False,
        skip_cache_recheck: bool = False,
    ) -> int:
        print("== Tier 1 API canary ==")
        await self.check_health()
        if not self.checks[-1].ok:
            return 1

        if not skip_sync_guard and profiles:
            await self.check_sync_guard(profiles[0].linkedin_url)

        first_photo_pass: CanaryProfile | None = None
        for profile in profiles:
            row = await self.run_profile(profile)
            self.rows.append(row)
            print(
                f"{row.status:4}  {row.category:14} {row.slug:24} "
                f"expect_photo={row.expect_photo} {row.detail}"
            )
            if (
                first_photo_pass is None
                and row.status == "PASS"
                and profile.expect_photo
            ):
                first_photo_pass = profile

        if not skip_cache_recheck and first_photo_pass is not None:
            await self.check_cache_recheck(first_photo_pass)

        failed_profiles = sum(1 for r in self.rows if r.status == "FAIL")
        failed_checks = sum(1 for c in self.checks if not c.ok)
        print(
            f"\nSummary: profiles pass={sum(1 for r in self.rows if r.status == 'PASS')} "
            f"fail={failed_profiles} skip={sum(1 for r in self.rows if r.status == 'SKIP')} "
            f"| checks fail={failed_checks}"
        )
        return 0 if failed_profiles == 0 and failed_checks == 0 else 1

    async def check_health(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/health")
            payload = response.json() if response.status_code == 200 else {}
            ok = response.status_code == 200 and payload.get("status") == "ok"
            self.record_check("api_health", ok, f"status={response.status_code}")
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            self.record_check("api_health", False, str(exc))

    async def check_sync_guard(self, linkedin_url: str) -> None:
        body = {"linkedin_url": linkedin_url, "requested_tiers": ["tier1"]}
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/enrich/sync",
                    headers=self.headers,
                    json=body,
                )
            if response.status_code != 200:
                self.record_check(
                    "sync_guard",
                    False,
                    f"status={response.status_code} body={response.text[:200]}",
                )
                return
            ok, detail = sync_guard_ok(response.json())
            self.record_check("sync_guard", ok, detail)
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            self.record_check("sync_guard", False, str(exc))

    async def check_cache_recheck(self, profile: CanaryProfile) -> None:
        row = await self.run_profile(profile)
        ok = row.status == "PASS"
        self.record_check(
            "cache_recheck",
            ok,
            f"slug={profile.slug} {row.detail}",
            job_id=row.job_id,
            asset_url=row.asset_url,
        )

    async def run_profile(self, profile: CanaryProfile) -> ProfileResult:
        body = {
            "linkedin_url": profile.linkedin_url,
            "requested_tiers": ["tier1"],
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                enqueue = await client.post(
                    f"{self.base_url}/enrich",
                    headers=self.headers,
                    json=body,
                )
            if enqueue.status_code != 202:
                return ProfileResult(
                    slug=profile.slug,
                    linkedin_url=profile.linkedin_url,
                    category=profile.category,
                    expect_photo=profile.expect_photo,
                    status="FAIL",
                    detail=f"enqueue status={enqueue.status_code} body={enqueue.text[:200]}",
                )
            job_id = str(enqueue.json()["id"])
            job = await self._poll_job(job_id)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
            return ProfileResult(
                slug=profile.slug,
                linkedin_url=profile.linkedin_url,
                category=profile.category,
                expect_photo=profile.expect_photo,
                status="FAIL",
                detail=str(exc),
            )

        status, detail = score_job_payload(job, expect_photo=profile.expect_photo)
        dossier = job.get("dossier") or {}
        photo = dossier.get("photo") or {}
        return ProfileResult(
            slug=profile.slug,
            linkedin_url=profile.linkedin_url,
            category=profile.category,
            expect_photo=profile.expect_photo,
            status=status,
            detail=detail,
            job_id=str(job.get("id") or job_id),
            job_status=str(job.get("status") or ""),
            asset_url=str(photo.get("asset_url") or "") or None,
            sources=[str(s) for s in (dossier.get("sources") or [])],
        )

    async def _poll_job(self, job_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.poll_timeout
        final: dict[str, Any] = {}
        async with httpx.AsyncClient(timeout=30.0) as client:
            while time.monotonic() < deadline:
                poll = await client.get(
                    f"{self.base_url}/enrich/{job_id}",
                    headers=self.headers,
                )
                final = poll.json()
                if final.get("status") not in {"queued", "running"}:
                    return final
                await asyncio.sleep(self.poll_interval)
        return final or {"status": "queued", "id": job_id, "dossier": {}}


def build_profiles(
    entries: list[dict[str, Any]],
    *,
    limit: int | None,
) -> tuple[list[CanaryProfile], list[ProfileResult]]:
    profiles: list[CanaryProfile] = []
    skips: list[ProfileResult] = []
    for entry in entries:
        profile, reason = parse_canary_profile(entry)
        if profile is None:
            skips.append(
                ProfileResult(
                    slug=str(entry.get("slug") or "(invalid)"),
                    linkedin_url=str(entry.get("linkedin_url") or ""),
                    category=str(entry.get("category") or "unknown"),
                    expect_photo=False,
                    status="SKIP",
                    detail=reason,
                )
            )
            continue
        profiles.append(profile)
        if limit is not None and len(profiles) >= limit:
            break
    return profiles, skips


def write_report(
    *,
    path: Path,
    rows: list[ProfileResult],
    checks: list[CheckResult],
    exit_code: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "exit_code": exit_code,
        "checks": [asdict(c) for c in checks],
        "rows": [asdict(r) for r in rows],
        "summary": {
            "pass": sum(1 for r in rows if r.status == "PASS"),
            "fail": sum(1 for r in rows if r.status == "FAIL"),
            "skip": sum(1 for r in rows if r.status == "SKIP"),
            "checks_failed": sum(1 for c in checks if not c.ok),
        },
    }
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport written to {path}")


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Tier 1 canary profiles through POST /enrich (API + worker)"
    )
    parser.add_argument("--file", required=True, help="JSON file with canary profiles")
    parser.add_argument(
        "--base-url",
        default=os.getenv("E2E_BASE_URL", DEFAULT_BASE_URL),
        help="API base URL (default E2E_BASE_URL or http://localhost:8000)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Run only first N valid profiles")
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=DEFAULT_POLL_TIMEOUT,
        help="Seconds to wait per job (default 300)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL,
        help="Seconds between polls (default 5)",
    )
    parser.add_argument("--skip-sync-guard", action="store_true")
    parser.add_argument("--skip-cache-recheck", action="store_true")
    parser.add_argument("--json", action="store_true", help="Write JSON report to .e2e-results/")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.is_file():
        print(f"Canary file not found: {path}")
        return 1

    try:
        entries = load_canary_entries(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid canary file: {exc}")
        return 1

    profiles, skip_rows = build_profiles(entries, limit=args.limit)
    settings = get_settings()
    runner = Tier1ApiCanary(
        base_url=args.base_url,
        token=settings.api_token,
        poll_timeout=args.poll_timeout,
        poll_interval=args.poll_interval,
    )
    runner.rows.extend(skip_rows)
    for row in skip_rows:
        print(f"SKIP  {row.category:14} {row.slug:24} {row.detail}")

    if not profiles and not skip_rows:
        print("No profiles in canary file")
        return 1

    exit_code = await runner.run(
        profiles,
        skip_sync_guard=args.skip_sync_guard,
        skip_cache_recheck=args.skip_cache_recheck,
    )

    if args.json:
        write_report(
            path=RESULTS_DIR / "tier1-api-canary.json",
            rows=runner.rows,
            checks=runner.checks,
            exit_code=exit_code,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
