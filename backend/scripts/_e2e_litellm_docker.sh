#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../docker"
REQ="$(dirname "$0")/_llm_chat_req.json"

echo "== models =="
curl -sf --max-time 20 http://127.0.0.1:4000/v1/models
echo

echo "== chat =="
curl -sf -X POST --max-time 90 http://127.0.0.1:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  --data-binary @"$REQ"
echo

echo "== rebuild api =="
docker compose --env-file ../.env --profile llm up -d --build api
sleep 5

echo "== settings =="
docker compose --env-file ../.env exec -T api \
  bash -lc 'cd /app/backend && python -c "from app.config import get_settings; s=get_settings(); print(s.llm_mode, s.litellm_api_base, s.litellm_model)"'

echo "== disambiguate =="
docker compose --env-file ../.env exec -i api \
  bash -lc 'cd /app/backend && python -' \
  < "$(dirname "$0")/_e2e_litellm_disambiguate.py"

echo "== enrich/sync =="
python3 "$(dirname "$0")/_probe_enrich_disambiguation.py"
echo "ALL E2E PASSED"
