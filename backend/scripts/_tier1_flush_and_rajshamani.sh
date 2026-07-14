#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

export MULTILOGIN_HOST_IP
MULTILOGIN_HOST_IP=$(ip route show default | awk '{print $3}')
echo "MULTILOGIN_HOST_IP=$MULTILOGIN_HOST_IP"

echo "=== FLUSH Redis (queue + caches) ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T redis redis-cli FLUSHDB

echo "=== Recreate worker ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml up -d --force-recreate worker
sleep 3
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker \
  cat /etc/hosts | grep -E 'launcher|host.docker' || true

echo "=== Launcher check ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T worker python - <<'PY'
import httpx
r = httpx.get("https://launcher.mlx.yt:45001/api/v2/", verify=False, timeout=5)
print("launcher", r.status_code)
PY

echo "=== POST rajshamani only ==="
RESP=$(curl -s -X POST http://localhost:8000/enrich \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -d '{"linkedin_url":"https://www.linkedin.com/in/rajshamani/?isSelfProfile=false","requested_tiers":["tier1"]}')
echo "$RESP"
JOB_ID=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['id'])" "$RESP")
echo "JOB_ID=$JOB_ID"

echo "=== Poll (watch Multilogin browser for /in/rajshamani/) ==="
for i in $(seq 1 72); do
  OUT=$(curl -s "http://localhost:8000/enrich/$JOB_ID" -H "Authorization: Bearer change-me")
  STATUS=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['status'])" "$OUT")
  echo "poll $i status=$STATUS"
  if [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]]; then
    echo "$OUT" | python3 -m json.tool
    break
  fi
  sleep 5
done

echo "=== Redis photo keys ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T redis redis-cli KEYS 'tier1:photo:*' || true

echo "=== Postgres photo_cache ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T postgres \
  psql -U hyrepath -d hyrepath -c "SELECT slug, asset_url FROM photo_cache WHERE slug = 'rajshamani';" || true

echo "=== Worker logs (tail) ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml logs worker --tail 60
