#!/usr/bin/env bash
# One-shot Tier1 Docker networking diagnosis (WSL + Docker Engine).
set -uo pipefail

service docker start >/dev/null 2>&1 || true

WIN_IP=$(ip route show default | awk '{print $3}')
echo "=== HOST / WSL Multilogin probes ==="
echo "WIN_IP=$WIN_IP"
echo -n "wsl->WIN:45001 = "
curl -sk -o /dev/null -w '%{http_code}' --connect-timeout 5 "https://${WIN_IP}:45001/api/v2/" || echo fail
echo
echo -n "wsl->127.0.0.1:45001 = "
curl -sk -o /dev/null -w '%{http_code}' --connect-timeout 5 "https://127.0.0.1:45001/api/v2/" || echo fail
echo

echo "=== worker container ==="
docker inspect docker-worker-1 --format 'Status={{.State.Status}} ExitCode={{.State.ExitCode}} FinishedAt={{.State.FinishedAt}}' 2>/dev/null || echo "no docker-worker-1"
echo -n "ExtraHosts="
docker inspect docker-worker-1 --format '{{json .HostConfig.ExtraHosts}}' 2>/dev/null || true
echo

echo "=== env presence (names only) ==="
docker inspect docker-worker-1 --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
  | awk -F= '
    /^(ENABLE_TIER1|BROWSER_MODE|MULTILOGIN_SELENIUM_HOST|MULTILOGIN_LAUNCHER_URL|MULTILOGIN_EMAIL|MULTILOGIN_PASSWORD|MULTILOGIN_FOLDER_ID|LINKEDIN_BOT_EMAIL|LINKEDIN_BOT_PASSWORD|R2_ACCOUNT_ID|R2_ACCESS_KEY_ID|R2_SECRET_ACCESS_KEY|R2_BUCKET|REDIS_URL|DATABASE_URL|APP_ENV)=/ {
      key=$1; val=substr($0, index($0,"=")+1);
      if (val=="") print key "=MISSING";
      else print key "=SET(" length(val) " chars)";
    }'

echo
echo "=== recreate worker with MULTILOGIN_HOST_IP ==="
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker
export MULTILOGIN_HOST_IP="$WIN_IP"
docker compose -f docker-compose.yml -f docker-compose.tier1.yml up -d --force-recreate worker

sleep 3
echo "=== /etc/hosts in worker ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker \
  sh -c "grep -E 'launcher|host.docker' /etc/hosts || true"

echo "=== launcher from worker ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker \
  python -c "import httpx; r=httpx.get('https://launcher.mlx.yt:45001/api/v2/', verify=False, timeout=5); print('launcher_status', r.status_code)"

echo "=== host.docker.internal from worker ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker \
  python -c "import httpx; r=httpx.get('https://host.docker.internal:45001/api/v2/', verify=False, timeout=5); print('hdi_status', r.status_code)"

echo "=== raw WIN_IP from worker ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker \
  python -c "import httpx,os; ip=os.environ.get('MULTILOGIN_HOST_IP',''); print('env_MULTILOGIN_HOST_IP', ip or '(unset)'); r=httpx.get(f'https://{ip}:45001/api/v2/', verify=False, timeout=5) if ip else None; print('raw_ip_status', getattr(r,'status_code', 'skipped'))"

echo "=== worker boot logs (tail) ==="
docker logs --tail 40 docker-worker-1 2>&1

echo "=== DONE ==="
