#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker
export MULTILOGIN_HOST_IP=$(ip route show default | awk '{print $3}')

# Ensure worker has correct hosts
docker compose -f docker-compose.yml -f docker-compose.tier1.yml up -d worker

docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker python - <<'PY'
import asyncio, json, time, urllib.request
from app.providers.multilogin import MultiloginClient
from app.providers.linkedin.client import LinkedInBrowserClient
from app.storage.r2 import R2StorageClient
from app.storage.photo_cache import PhotoCache
from app.domain.dossier import PhotoAsset
from datetime import datetime, timezone
import hashlib
from app.storage.r2 import object_key_with_extension

URL = "https://www.linkedin.com/in/rajshamani/?isSelfProfile=false"

async def main() -> None:
    mlx = MultiloginClient()
    token = await mlx.sign_in(force=True)
    ids = await mlx.list_profiles(token)
    print("profiles", ids)
    for pid in ids:
        try:
            await mlx.stop_profile(pid, token)
            print("stopped", pid)
        except Exception as e:
            print("stop_err", pid, e)
    # Prefer first profile only
    client = LinkedInBrowserClient()
    print("scraping...")
    result = await asyncio.wait_for(
        client.scrape_photo(URL, job_id="live-rajshamani"),
        timeout=240,
    )
    print("outcome", getattr(result.outcome, "value", result.outcome))
    print("bytes", len(result.image_bytes or b""))
    if not result.image_bytes:
        return
    storage = R2StorageClient()
    asset_url = await storage.upload_bytes(
        "linkedin/rajshamani",
        result.image_bytes,
        content_type=result.content_type or "image/jpeg",
    )
    print("asset_url", asset_url)
    photo = PhotoAsset(
        source="linkedin-photo",
        asset_url=asset_url,
        captured_at=datetime.now(timezone.utc),
        confidence=result.confidence,
    )
    cache = PhotoCache()
    await cache.put(
        "rajshamani",
        photo,
        asset_key=object_key_with_extension("linkedin/rajshamani", result.content_type or "image/jpeg"),
        extraction_method=result.method.value if result.method else "",
        content_hash=hashlib.sha256(result.image_bytes).hexdigest(),
    )
    cached = await cache.get("rajshamani")
    print("cache_hit", bool(cached), getattr(cached, "asset_url", None))

asyncio.run(main())
PY
