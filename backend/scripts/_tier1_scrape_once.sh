#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

# Stop leftover MLX profiles, then run full scrape_photo once inside worker
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker python - <<'PY'
import asyncio
import traceback
from app.clients.multilogin import MultiloginClient
from app.integrations.linkedin.client import LinkedInBrowserClient

async def main() -> None:
    mlx = MultiloginClient()
    token = await mlx.get_token()
    for pid in await mlx.list_profiles(token):
        try:
            await mlx.stop_profile(pid, token)
            print("stopped", pid)
        except Exception as e:
            print("stop_fail", pid, e)
    client = LinkedInBrowserClient()
    try:
        result = await client.scrape_photo(
            "https://www.linkedin.com/in/rajshamani/?isSelfProfile=false",
            job_id="manual-probe",
        )
        print("outcome", result.outcome)
        print("method", result.method)
        print("bytes", len(result.image_bytes or b""))
        print("content_type", result.content_type)
        print("confidence", result.confidence)
    except Exception:
        traceback.print_exc()

asyncio.run(main())
PY
