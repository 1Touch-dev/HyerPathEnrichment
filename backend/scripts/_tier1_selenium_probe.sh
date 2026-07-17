#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker
export MULTILOGIN_HOST_IP
MULTILOGIN_HOST_IP=${MULTILOGIN_HOST_IP:-$(ip route show default | awk '{print $3}')}
echo "MULTILOGIN_HOST_IP=$MULTILOGIN_HOST_IP"
docker compose -f docker-compose.yml -f docker-compose.tier1.yml up -d --force-recreate worker
sleep 2
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker cat /etc/hosts | grep -E 'launcher|host.docker' || true

docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker python - <<'PY'
import asyncio
import httpx
from selenium import webdriver
from selenium.webdriver.chromium.options import ChromiumOptions
from app.core.config import get_settings
from app.clients.multilogin import MultiloginClient

async def main() -> None:
    s = get_settings()
    mlx = MultiloginClient()
    token = await mlx.sign_in(force=True)
    ids = await mlx.list_profiles(token)
    print("profiles", ids)
    pid = ids[0]
    # stop first
    try:
        await mlx.stop_profile(pid, token)
    except Exception as e:
        print("prestop", e)
    port = await mlx.start_profile(pid, token)
    print("started port", port, "selenium_host", s.multilogin_selenium_host)
    # quick TCP check
    host = s.multilogin_selenium_host.replace("http://", "").replace("https://", "").rstrip("/")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(f"http://{host}:{port}/status")
            print("selenium_status", r.status_code, r.text[:200])
        except Exception as e:
            print("selenium_http", type(e).__name__, e)
    options = ChromiumOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    print("connecting selenium...")
    driver = webdriver.Remote(command_executor=f"{s.multilogin_selenium_host.rstrip('/')}:{port}", options=options)
    driver.set_page_load_timeout(60)
    print("title_before", driver.title)
    driver.get("https://www.linkedin.com/in/rajshamani/")
    print("url", driver.current_url)
    print("title", driver.title)
    driver.quit()
    await mlx.stop_profile(pid, token)
    print("done")

asyncio.run(main())
PY
