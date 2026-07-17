#!/usr/bin/env bash
# Narrow probe: launcher OK? start profile? TCP to selenium port?
set -uo pipefail
service docker start >/dev/null 2>&1 || true
export MULTILOGIN_HOST_IP=$(ip route show default | awk '{print $3}')
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

echo "WIN_IP=$MULTILOGIN_HOST_IP"
docker compose -f docker-compose.yml -f docker-compose.tier1.yml up -d worker >/dev/null
sleep 2

docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker python -u - <<'PY'
import asyncio
import socket
import sys
import httpx
from app.core.config import get_settings
from app.providers.multilogin import MultiloginClient

def tcp_check(host: str, port: int, timeout: float = 5.0) -> str:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return "OPEN"
    except Exception as exc:
        return f"FAIL:{type(exc).__name__}:{exc}"

async def main() -> None:
    s = get_settings()
    host = s.multilogin_selenium_host.replace("http://", "").replace("https://", "").rstrip("/")
    print("selenium_host", host, flush=True)
    print("launcher_url", s.multilogin_launcher_url, flush=True)

    # 1) launcher API
    try:
        async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
            r = await client.get("https://launcher.mlx.yt:45001/api/v2/")
            print("launcher_http", r.status_code, flush=True)
    except Exception as e:
        print("launcher_http FAIL", type(e).__name__, e, flush=True)
        return

    print("tcp_45001", tcp_check(host, 45001), flush=True)

    mlx = MultiloginClient()
    print("signing_in...", flush=True)
    token = await mlx.sign_in(force=True)
    print("signed_in token_len", len(token), flush=True)
    ids = await mlx.list_profiles(token)
    print("profiles", ids, flush=True)
    if not ids:
        return
    pid = ids[0]

    try:
        await mlx.stop_profile(pid, token)
        print("prestop ok", flush=True)
    except Exception as e:
        print("prestop", type(e).__name__, e, flush=True)

    print("starting_profile...", flush=True)
    try:
        port = await asyncio.wait_for(mlx.start_profile(pid, token), timeout=90)
    except Exception as e:
        print("start_profile FAIL", type(e).__name__, e, flush=True)
        return
    print("started_port", port, flush=True)

    print("tcp_selenium_port", tcp_check(host, int(port), timeout=5.0), flush=True)
    print("tcp_127_from_container", tcp_check("127.0.0.1", int(port), timeout=2.0), flush=True)

    # HTTP status endpoint (Selenium)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"http://{host}:{port}/status")
            print("selenium_status_http", r.status_code, (r.text or "")[:160], flush=True)
    except Exception as e:
        print("selenium_status_http FAIL", type(e).__name__, e, flush=True)

    # Selenium Remote with hard socket-ish timeout via wait_for thread
    from selenium import webdriver
    from selenium.webdriver.chromium.options import ChromiumOptions

    def connect():
        options = ChromiumOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Remote(
            command_executor=f"{s.multilogin_selenium_host.rstrip('/')}:{port}",
            options=options,
        )
        title = driver.title
        driver.quit()
        return title

    print("selenium_remote_connect...", flush=True)
    try:
        title = await asyncio.wait_for(asyncio.to_thread(connect), timeout=30)
        print("selenium_remote OK title=", title, flush=True)
    except Exception as e:
        print("selenium_remote FAIL", type(e).__name__, e, flush=True)

    try:
        await mlx.stop_profile(pid, token)
        print("poststop ok", flush=True)
    except Exception as e:
        print("poststop", type(e).__name__, e, flush=True)

asyncio.run(main())
print("PROBE_DONE", flush=True)
PY
