"""Local Multilogin LinkedIn photo scrape + R2 upload + photo cache (no Docker worker).

1. Checks Multilogin launcher on the host
2. Scrapes the profile photo via LinkedInBrowserClient
3. Uploads to R2 (or .asset-cache fallback if R2 unset)
4. Writes Redis + SQL photo_cache entry (same as LinkedInPhotoEnricher)
5. Also saves a local copy under backend/artifacts/tier1/ for inspection

Prerequisites:
  - Multilogin X running on Windows (port 45001)
  - backend/.env with MULTILOGIN_*, LINKEDIN_BOT_*, R2_* filled
  - MULTILOGIN_SELENIUM_HOST=http://127.0.0.1
  - Redis reachable at REDIS_URL (optional — SQL cache still written if Redis is down)
  - pip install -e ".[enrichers]" in a venv

Usage (from backend/):
  python scripts/local_multilogin_scrape_test.py
  python scripts/local_multilogin_scrape_test.py --linkedin-url https://www.linkedin.com/in/someone/
  python scripts/local_multilogin_scrape_test.py --launcher-only
  python scripts/local_multilogin_scrape_test.py --skip-scrape  # re-check cache for slug only
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.models import PhotoAsset
from app.providers.linkedin.urls import extract_linkedin_slug
from app.providers.linkedin_browser import LinkedInBrowserClient, LinkedInPhotoError
from app.database.session import init_db
from app.storage.photo_cache import PhotoCache, _redis_key, slug_hash
from app.storage.r2 import R2StorageClient, R2StorageError, object_key_with_extension, r2_is_configured
from app.infrastructure.redis import get_redis_client

DEFAULT_URL = "https://www.linkedin.com/in/rajshamani/?isSelfProfile=false"
OUT_DIR = ROOT / "artifacts" / "tier1"


async def check_launcher(settings) -> int:
    """Return 0 if Multilogin launcher answers on the configured URL."""
    base = settings.multilogin_launcher_url.rstrip("/")
    url = f"{base}/"
    print(f"Checking launcher: {url}")
    print(f"Selenium host:     {settings.multilogin_selenium_host}")
    try:
        async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
            response = await client.get(url)
        print(f"Launcher HTTP {response.status_code} (up)")
        return 0
    except httpx.HTTPError as exc:
        print(f"Launcher unreachable: {exc}")
        print(
            "Start Multilogin X on Windows and retry "
            "(PowerShell: curl.exe -sk https://127.0.0.1:45001/api/v2/)."
        )
        return 1


def _extension(content_type: str | None) -> str:
    normalized = (content_type or "image/jpeg").split(";")[0].strip().lower()
    return {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
    }.get(normalized, "jpg")


def _safe_slug(linkedin_url: str) -> str:
    slug = extract_linkedin_slug(linkedin_url) or "profile"
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", slug)[:64]


async def verify_cache(slug: str) -> None:
    cache = PhotoCache()
    cached = await cache.get(slug)
    if cached is None:
        print("Cache get: MISS")
        return
    print(f"Cache get: HIT asset_url={cached.asset_url} confidence={cached.confidence}")
    try:
        raw = await get_redis_client().get(_redis_key(slug))
        print(f"Redis key: {_redis_key(slug)} present={bool(raw)}")
    except Exception as exc:
        print(f"Redis check skipped: {exc}")
    print(f"SQL slug_hash: {slug_hash(slug)}")


async def scrape_upload_cache(*, linkedin_url: str, skip_local_file: bool) -> int:
    settings = get_settings()
    if not settings.enable_tier1:
        print("WARN: ENABLE_TIER1 is false — production worker would skip Tier 1.")
    if settings.browser_mode.strip().lower() != "multilogin":
        print(f"WARN: BROWSER_MODE={settings.browser_mode!r} (expected multilogin).")

    if await check_launcher(settings) != 0:
        return 1

    if r2_is_configured(settings):
        print(f"R2: configured bucket={settings.r2_bucket} public={settings.r2_public_base_url}")
    else:
        print("R2: NOT fully configured — upload will use local .asset-cache/ fallback")

    slug = _safe_slug(linkedin_url)
    print(f"Scraping {linkedin_url} (slug={slug})...")

    client = LinkedInBrowserClient()
    result = await client.scrape_photo(linkedin_url, job_id=f"local-{slug}")
    if result.outcome != LinkedInPhotoError.SUCCESS or not result.image_bytes:
        print(f"Scrape failed: outcome={result.outcome}")
        return 1

    content_type = result.content_type or "image/jpeg"
    print(f"Scrape OK: {len(result.image_bytes)} bytes method={result.method} confidence={result.confidence}")

    if not skip_local_file:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = OUT_DIR / f"local_mlx_{slug}_{stamp}.{_extension(content_type)}"
        out.write_bytes(result.image_bytes)
        print(f"Local copy: {out}")

    asset_key_base = f"linkedin/{slug}"
    storage = R2StorageClient()
    try:
        asset_url = await storage.upload_bytes(
            asset_key_base,
            result.image_bytes,
            content_type=content_type,
        )
    except R2StorageError as exc:
        print(f"R2 upload failed: {exc}")
        return 1

    object_key = object_key_with_extension(asset_key_base, content_type)
    print(f"Upload OK: key={object_key}")
    print(f"  asset_url={asset_url}")

    await init_db()
    photo = PhotoAsset(
        source="linkedin-photo",
        asset_url=asset_url,
        captured_at=datetime.now(timezone.utc),
        confidence=result.confidence,
    )
    cache = PhotoCache()
    await cache.put(
        slug,
        photo,
        asset_key=object_key,
        extraction_method=result.method.value if result.method else "",
        content_hash=hashlib.sha256(result.image_bytes).hexdigest(),
    )
    print("Photo cache put: OK (SQL + Redis when available)")
    await verify_cache(slug)
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local Multilogin scrape → R2 upload → photo_cache"
    )
    parser.add_argument(
        "--linkedin-url",
        default=DEFAULT_URL,
        help="LinkedIn /in/{slug} URL to scrape",
    )
    parser.add_argument(
        "--launcher-only",
        action="store_true",
        help="Only check Multilogin launcher reachability",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip scrape/upload; only verify existing cache for the URL slug",
    )
    parser.add_argument(
        "--skip-local-file",
        action="store_true",
        help="Do not write a copy under artifacts/tier1/",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.launcher_only:
        return await check_launcher(settings)

    if args.skip_scrape:
        await init_db()
        slug = _safe_slug(args.linkedin_url)
        print(f"Checking cache for slug={slug}")
        await verify_cache(slug)
        return 0

    return await scrape_upload_cache(
        linkedin_url=args.linkedin_url,
        skip_local_file=args.skip_local_file,
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
