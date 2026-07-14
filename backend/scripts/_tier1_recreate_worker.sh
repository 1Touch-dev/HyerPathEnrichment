#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

MULTILOGIN_HOST_IP=$(ip route show default | awk '{print $3}')
export MULTILOGIN_HOST_IP
echo "MULTILOGIN_HOST_IP=$MULTILOGIN_HOST_IP"

code=$(curl -sk -o /dev/null -w "%{http_code}" --connect-timeout 5 "https://${MULTILOGIN_HOST_IP}:45001/api/v2/" || true)
echo "host_probe:$code"
if [[ "$code" == "000" || -z "$code" ]]; then
  echo "ERROR: Multilogin not reachable at ${MULTILOGIN_HOST_IP}:45001 — start Multilogin X on Windows first"
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.tier1.yml up -d --force-recreate worker

echo "--- /etc/hosts in worker ---"
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker cat /etc/hosts | grep -E 'launcher|host.docker' || true

echo "--- launcher from worker ---"
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker python - <<'PY'
import httpx
r = httpx.get("https://launcher.mlx.yt:45001/api/v2/", verify=False, timeout=5)
print(r.status_code)
PY
