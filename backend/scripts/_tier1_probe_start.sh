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
    print("api_url", s.multilogin_api_url)
    print("launcher_url", s.multilogin_launcher_url)
    print("selenium_host", s.multilogin_selenium_host)
    print("folder", s.multilogin_folder_id)
    print("enable_tier1", s.enable_tier1, "browser", s.browser_mode)
    mlx = MultiloginClient()
    token = await mlx.sign_in(force=True)
    print("token_len", len(token))
    ids = await mlx.list_profiles(token)
    print("profiles", len(ids), ids[:3])
    if not ids:
        return
    pid = ids[0]
    folder = s.multilogin_folder_id
    url = f"{s.multilogin_launcher_url.rstrip('/')}/profile/f/{folder}/p/{pid}/start"
    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        r = await client.get(
            url,
            params={"automation_type": "selenium"},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"},
        )
        print("start_status", r.status_code)
        print("start_body", (r.text or "")[:800])

asyncio.run(main())
PY
