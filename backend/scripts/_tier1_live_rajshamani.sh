#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

API=http://localhost:8000
AUTH="Authorization: Bearer change-me"
URL='https://www.linkedin.com/in/rajshamani/?isSelfProfile=false'

echo "=== POST enrich (cache miss expected) ==="
RESP=$(curl -s -X POST "$API/enrich" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"linkedin_url\": \"$URL\", \"requested_tiers\": [\"tier1\"]}")
echo "$RESP"
JOB_ID=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['id'])" "$RESP")
echo "JOB_ID=$JOB_ID"

echo "=== Poll until completed ==="
for i in $(seq 1 60); do
  OUT=$(curl -s "$API/enrich/$JOB_ID" -H "$AUTH")
  STATUS=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['status'])" "$OUT")
  echo "poll $i status=$STATUS"
  if [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]]; then
    echo "$OUT" | python3 -m json.tool
    break
  fi
  sleep 5
done

PHOTO=$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print((d.get('dossier') or {}).get('photo') or {})" "$OUT")
echo "PHOTO=$PHOTO"

echo "=== Redis keys ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T redis redis-cli KEYS 'tier1:photo:*' || true

echo "=== Postgres photo_cache ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec -T postgres \
  psql -U hyrepath -d hyrepath -c "SELECT slug, asset_url, extraction_method FROM photo_cache WHERE slug = 'rajshamani';" || true

echo "=== POST enrich again (cache hit expected) ==="
RESP2=$(curl -s -X POST "$API/enrich" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"linkedin_url\": \"https://www.linkedin.com/in/rajshamani/\", \"requested_tiers\": [\"tier1\"]}")
JOB2=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['id'])" "$RESP2")
for i in $(seq 1 30); do
  OUT2=$(curl -s "$API/enrich/$JOB2" -H "$AUTH")
  STATUS2=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['status'])" "$OUT2")
  if [[ "$STATUS2" == "completed" || "$STATUS2" == "failed" ]]; then
    echo "$OUT2" | python3 -m json.tool
    break
  fi
  sleep 2
done

echo "=== recent worker logs ==="
docker compose -f docker-compose.yml -f docker-compose.tier1.yml logs worker --tail 80
