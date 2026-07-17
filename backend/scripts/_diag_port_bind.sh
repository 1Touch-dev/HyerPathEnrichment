#!/usr/bin/env bash
# Confirm: Selenium port reachable on Windows loopback but NOT via WIN_IP from WSL/Docker.
set -uo pipefail
service docker start >/dev/null 2>&1 || true
export MULTILOGIN_HOST_IP=$(ip route show default | awk '{print $3}')
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker
docker compose -f docker-compose.yml -f docker-compose.tier1.yml up -d worker >/dev/null
sleep 2

# Start profile inside worker, print port only, leave profile running briefly
PORT=$(docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker python -u - <<'PY'
import asyncio
from app.clients.multilogin import MultiloginClient

async def main() -> None:
    mlx = MultiloginClient()
    token = await mlx.sign_in(force=True)
    pid = (await mlx.list_profiles(token))[0]
    try:
        await mlx.stop_profile(pid, token)
    except Exception:
        pass
    port = await mlx.start_profile(pid, token)
    print(port)

asyncio.run(main())
PY
)
PORT=$(echo "$PORT" | tr -d '\r' | tail -n1)
echo "SELENIUM_PORT=$PORT"
echo "WIN_IP=$MULTILOGIN_HOST_IP"

echo -n "wsl_tcp_WIN_IP:port = "
timeout 5 bash -c "echo >/dev/tcp/${MULTILOGIN_HOST_IP}/${PORT}" 2>/dev/null && echo OPEN || echo CLOSED_OR_TIMEOUT

echo -n "wsl_tcp_127:port = "
timeout 3 bash -c "echo >/dev/tcp/127.0.0.1/${PORT}" 2>/dev/null && echo OPEN || echo CLOSED_OR_TIMEOUT

# From inside worker again
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker python -u - <<PY
import socket
port = int("$PORT")
for host in ("launcher.mlx.yt", "host.docker.internal", "172.26.128.1", "127.0.0.1"):
    try:
        with socket.create_connection((host, port), timeout=4.0):
            print(f"docker_tcp {host}:{port} OPEN")
    except Exception as e:
        print(f"docker_tcp {host}:{port} FAIL {type(e).__name__}")
PY

# Stop profile
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker python -u - <<'PY'
import asyncio
from app.clients.multilogin import MultiloginClient
async def main():
    mlx = MultiloginClient()
    token = await mlx.sign_in(force=True)
    pid = (await mlx.list_profiles(token))[0]
    try:
        await mlx.stop_profile(pid, token)
        print("stopped")
    except Exception as e:
        print("stop_fail", e)
asyncio.run(main())
PY
