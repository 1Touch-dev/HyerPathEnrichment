"""Run ONE real profile through the full Tier 1-4 pipeline via the real API.

Unlike ``e2e_tier1_canary.py`` / ``probe_enrichers.py --canary`` (which iterate
a 20-profile canary set), this script sends a single ``POST /enrich`` with
``requested_tiers=["tier1","tier2","tier3","tier4"]`` for one named person —
exactly what a real customer request looks like — then polls the job to
completion and prints the merged dossier.

Usage:
  cd backend
  python scripts/run_real_world_single_profile.py
  python scripts/run_real_world_single_profile.py --base-url http://localhost:8000 --json

Requires a running API + Redis + RQ worker with ENABLE_TIER1=true and
Multilogin reachable from the worker. Live LinkedIn/GitHub/Google Maps calls
only — not for CI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
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

RESULTS_DIR = ROOT / ".e2e-results"
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_POLL_TIMEOUT = 900.0
DEFAULT_POLL_INTERVAL = 10.0

# Nithin Kamath (CEO, Zerodha) — the one real profile for this run.
# username/business are public-record best guesses (X handle @Nithin0dha,
# Zerodha HQ) since only linkedin_url + name/role/company were supplied.
DEFAULT_PROFILE: dict[str, str] = {
    "linkedin_url": "https://www.linkedin.com/in/nithin-kamath-81136242/",
    "username": "Nithin0dha",
    "company": "Zerodha",
    "business": "Zerodha Bengaluru",
}
DEFAULT_TIERS = ["tier1", "tier2", "tier3", "tier4"]


@dataclass
class RunResult:
    job_id: str | None
    status: str
    detail: str
    dossier: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0


def unwrap_envelope(payload: Any) -> dict[str, Any]:
    """Unwrap the shared ``{success, data}`` response envelope (EnvelopeAPIRoute)."""
    if isinstance(payload, dict) and "success" in payload and "data" in payload:
        data = payload.get("data")
        return data if isinstance(data, dict) else {}
    return payload if isinstance(payload, dict) else {}


def build_request_body(args: argparse.Namespace) -> dict[str, Any]:
    body: dict[str, Any] = {
        "linkedin_url": args.linkedin_url or DEFAULT_PROFILE["linkedin_url"],
        "username": args.username or DEFAULT_PROFILE["username"],
        "company": args.company or DEFAULT_PROFILE["company"],
        "business": args.business or DEFAULT_PROFILE["business"],
        "requested_tiers": args.tiers,
    }
    if args.email:
        body["email"] = args.email
    if args.job_search:
        body["job_search"] = args.job_search
    return {k: v for k, v in body.items() if v not in (None, "")}


async def poll_job(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    job_id: str,
    *,
    poll_timeout: float,
    poll_interval: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + poll_timeout
    final: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = await client.get(f"{base_url}/enrich/{job_id}", headers=headers)
        final = unwrap_envelope(response.json())
        status = str(final.get("status") or "")
        print(
            f"  ... status={status or 'unknown'} ({time.monotonic() - (deadline - poll_timeout):.0f}s elapsed)"
        )
        if status not in {"queued", "running"}:
            return final
        await asyncio.sleep(poll_interval)
    return final or {"status": "queued", "id": job_id, "dossier": {}}


def print_dossier(dossier: dict[str, Any]) -> None:
    print("\n== merged dossier ==")
    photo = dossier.get("photo") or {}
    print(
        f"photo: asset_url={photo.get('asset_url') or '(none)'} confidence={photo.get('confidence')}"
    )
    handles = dossier.get("handles") or []
    print(f"handles ({len(handles)}):")
    for h in handles:
        print(
            f"  - {h.get('platform')}: {h.get('username')} ({h.get('profile_url')}) confidence={h.get('confidence')}"
        )
    emails = dossier.get("emails") or []
    verified = dossier.get("verified_emails") or []
    print(f"emails: {emails}")
    print(f"verified_emails ({len(verified)}):")
    for e in verified:
        print(
            f"  - {e.get('value')} status={e.get('status')} confidence={e.get('confidence')} source={e.get('source')}"
        )
    github = dossier.get("github") or {}
    print(f"github: {github or '(empty)'}")
    coworkers = dossier.get("coworkers") or []
    print(f"coworkers ({len(coworkers)}): {coworkers}")
    jobs = dossier.get("jobs") or []
    print(f"jobs ({len(jobs)}):")
    for j in jobs:
        print(
            f"  - {j.get('title')} @ {j.get('company')} ({j.get('location')}) remote={j.get('remote')} source={j.get('source')}"
        )
    business = dossier.get("business")
    print(f"business: {business or '(none)'}")
    print(f"sources: {dossier.get('sources') or []}")
    confidence = dossier.get("confidence") or []
    if confidence:
        print("confidence breakdown:")
        for c in confidence:
            print(f"  - {c.get('label')}: {c.get('score')} evidence={c.get('evidence')}")


async def run(args: argparse.Namespace) -> RunResult:
    settings = get_settings()
    base_url = args.base_url.rstrip("/")
    token = args.token or settings.api_token
    headers = {"Authorization": f"Bearer {token}"}
    body = build_request_body(args)

    print("== real-world single-profile run ==")
    print(f"POST {base_url}/enrich  tiers={body.get('requested_tiers')}")
    print(
        f"identifiers: linkedin_url={body.get('linkedin_url')} username={body.get('username')} "
        f"company={body.get('company')} business={body.get('business')} email={body.get('email')}"
    )

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            enqueue = await client.post(f"{base_url}/enrich", headers=headers, json=body)
        except httpx.HTTPError as exc:
            return RunResult(job_id=None, status="FAIL", detail=f"enqueue error: {exc}")

        if enqueue.status_code != 202:
            return RunResult(
                job_id=None,
                status="FAIL",
                detail=f"enqueue status={enqueue.status_code} body={enqueue.text[:300]}",
            )

        job_id = str(unwrap_envelope(enqueue.json())["id"])
        print(f"job_id={job_id} — polling until completed (timeout={args.poll_timeout:.0f}s)")

        job = await poll_job(
            client,
            base_url,
            headers,
            job_id,
            poll_timeout=args.poll_timeout,
            poll_interval=args.poll_interval,
        )

    duration = time.perf_counter() - start
    status = str(job.get("status") or "")
    dossier = job.get("dossier") or {}

    if status == "completed":
        print_dossier(dossier)
        return RunResult(
            job_id=job_id,
            status="PASS",
            detail=f"job completed in {duration:.1f}s, sources={dossier.get('sources')}",
            dossier=dossier,
            duration_seconds=round(duration, 3),
        )
    if status in {"queued", "running"}:
        return RunResult(
            job_id=job_id,
            status="FAIL",
            detail=f"timeout waiting for job (last status={status})",
            dossier=dossier,
            duration_seconds=round(duration, 3),
        )
    return RunResult(
        job_id=job_id,
        status="FAIL",
        detail=f"job status={status!r}",
        dossier=dossier,
        duration_seconds=round(duration, 3),
    )


def write_report(result: RunResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "job_id": result.job_id,
        "status": result.status,
        "detail": result.detail,
        "duration_seconds": result.duration_seconds,
        "dossier": result.dossier,
    }
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport written to {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one real profile through Tier 1-4 via POST /enrich (API + worker)"
    )
    parser.add_argument(
        "--linkedin-url", default=None, help="Overrides the default Nithin Kamath LinkedIn URL"
    )
    parser.add_argument("--username", default=None)
    parser.add_argument("--company", default=None)
    parser.add_argument("--business", default=None)
    parser.add_argument("--job-search", default=None)
    parser.add_argument("--email", default=None)
    parser.add_argument(
        "--tiers",
        nargs="+",
        default=DEFAULT_TIERS,
        help="Requested tiers (default: tier1 tier2 tier3 tier4)",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("E2E_BASE_URL", DEFAULT_BASE_URL),
        help="API base URL (default E2E_BASE_URL or http://localhost:8000)",
    )
    parser.add_argument(
        "--token", default=None, help="Bearer token (default: settings.api_token from .env)"
    )
    parser.add_argument("--poll-timeout", type=float, default=DEFAULT_POLL_TIMEOUT)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--json", action="store_true", help="Write JSON report to .e2e-results/")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    result = await run(args)
    print(f"\n{result.status}  {result.detail}")

    if args.json:
        write_report(result, RESULTS_DIR / "real-world-single-profile-report.json")

    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
