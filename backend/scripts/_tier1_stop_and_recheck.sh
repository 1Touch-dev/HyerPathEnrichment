#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker python - <<'PY'
import asyncio
import httpx
from app.config import get_settings
from app.providers.multilogin import MultiloginClient

async def main() -> None:
    s = get_settings()
    mlx = MultiloginClient()
    token = await mlx.get_token()
    # Stop any running profiles from the probe
    for pid in await mlx.list_profiles(token):
        try:
            await mlx.stop_profile(pid, token)
            print("stopped", pid)
        except Exception as e:
            print("stop", pid, type(e).__name__, e)
    # Retry start with default SSL verify (same as app code)
    pid = (await mlx.list_profiles(token))[0]
    url = f"{s.multilogin_launcher_url.rstrip('/')}/profile/f/{s.multilogin_folder_id}/p/{pid}/start"
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            url,
            params={"automation_type": "selenium"},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"},
        )
        print("start_verify_default", r.status_code, (r.text or "")[:300])
    if r.status_code == 200:
        await mlx.stop_profile(pid, token)
        print("cleaned", pid)

asyncio.run(main())
PY
