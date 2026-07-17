"""Run a Tier 1 canary set and record scrape outcomes for manual QA.

Usage:
  cd backend
  python scripts/probe_tier1_canary.py --file docs/tier1_canary_set.example.json
  python scripts/probe_tier1_canary.py --file my_canary.json --json

Copy ``docs/tier1_canary_set.example.json`` to your own file with ~20 real
public profile URLs. Live MLX/LinkedIn calls only — not for CI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.integrations.linkedin.browser_facade import LinkedInBrowserClient, LinkedInPhotoError, extract_linkedin_slug
from app.integrations.multilogin.profile_pool import ProfilePool
from app.storage.photo_cache import PhotoCache


@dataclass
class CanaryRow:
    slug: str
    linkedin_url: str
    category: str
    status: str
    outcome: str
    bytes_len: int
    method: str | None
    confidence: float
    note: str = ""


async def run_canary(path: Path) -> list[CanaryRow]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("canary file must be a JSON array")

    browser = LinkedInBrowserClient()
    cache = PhotoCache()
    pool = ProfilePool()
    rows: list[CanaryRow] = []

    for entry in entries:
        url = str(entry.get("linkedin_url") or "").strip()
        slug = extract_linkedin_slug(url) or str(entry.get("slug") or "").strip().lower()
        category = str(entry.get("category") or "unknown")

        if not url or not slug:
            rows.append(
                CanaryRow(
                    slug=slug or "(invalid)",
                    linkedin_url=url,
                    category=category,
                    status="SKIP",
                    outcome="invalid_url",
                    bytes_len=0,
                    method=None,
                    confidence=0.0,
                    note="missing linkedin_url or slug",
                )
            )
            continue

        cached = await cache.get(slug)
        if cached:
            rows.append(
                CanaryRow(
                    slug=slug,
                    linkedin_url=url,
                    category=category,
                    status="CACHE_HIT",
                    outcome=LinkedInPhotoError.SUCCESS.value,
                    bytes_len=0,
                    method="cache",
                    confidence=cached.confidence,
                )
            )
            continue

        result = await browser.scrape_photo(url, job_id=f"canary-{slug}")
        rows.append(
            CanaryRow(
                slug=slug,
                linkedin_url=url,
                category=category,
                status="OK" if result.outcome == LinkedInPhotoError.SUCCESS else "FAIL",
                outcome=result.outcome.value,
                bytes_len=len(result.image_bytes or b""),
                method=result.method.value if result.method else None,
                confidence=result.confidence,
            )
        )

    return rows


def print_summary(rows: list[CanaryRow], pool_rows: list[dict]) -> None:
    ok = sum(1 for row in rows if row.status in {"OK", "CACHE_HIT"})
    fail = sum(1 for row in rows if row.status == "FAIL")
    skip = sum(1 for row in rows if row.status == "SKIP")
    print("\n== canary summary ==")
    print(f"total={len(rows)} ok/cache={ok} fail={fail} skip={skip}")
    for row in rows:
        print(
            f"{row.status:10} {row.category:14} {row.slug:24} "
            f"outcome={row.outcome} bytes={row.bytes_len} method={row.method}"
        )
    if pool_rows:
        print("\n== profile pool ==")
        for item in pool_rows:
            print(
                f"{item['profile_id']} views={item['views_today']}/{item['daily_limit']} "
                f"cooldown={item['in_cooldown']} eligible={item['eligible']}"
            )


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run Tier 1 canary profile set")
    parser.add_argument("--file", required=True, help="JSON file with canary profiles")
    parser.add_argument("--json", action="store_true", help="Write JSON report to .e2e-results/")
    parser.add_argument("--pool-status", action="store_true", help="Print MLX profile pool status")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.is_file():
        print(f"Canary file not found: {path}")
        return 1

    rows = await run_canary(path)
    pool_rows = await ProfilePool().pool_status() if args.pool_status else []
    print_summary(rows, pool_rows)

    if args.json:
        out_dir = ROOT / ".e2e-results"
        out_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rows": [asdict(row) for row in rows],
            "pool_status": pool_rows,
            "summary": {
                "total": len(rows),
                "ok_or_cache": sum(1 for row in rows if row.status in {"OK", "CACHE_HIT"}),
                "fail": sum(1 for row in rows if row.status == "FAIL"),
                "skip": sum(1 for row in rows if row.status == "SKIP"),
            },
        }
        out_path = out_dir / "probe-tier1-canary.json"
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nReport written to {out_path}")

    return 0 if all(row.status != "FAIL" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
