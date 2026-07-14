#!/usr/bin/env bash
# Tier 2 full E2E: Sherlock / Maigret / Social Analyzer + litellm disambiguation.
#
# Stage A (free path): compose api/worker/redis/postgres/social-analyzer,
# CLI prereqs, SA contract, isolation probes, sync + async enrich.
# Stage B (litellm): requires OPENAI_API_KEY or GEMINI_API_KEY in backend/.env.
#
# Usage:
#   bash backend/scripts/e2e_tier2.sh
#
# Windows (WSL):
#   wsl -d Ubuntu-22.04 -u root bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/e2e_tier2.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$BACKEND_DIR/.env"
BASE="http://localhost:8000"

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1" >&2; exit 1; }

mkdir -p "$BACKEND_DIR/.e2e-results"
service docker start >/dev/null 2>&1 || true

if [ ! -f "$ENV_FILE" ]; then
  fail "missing $ENV_FILE (needed for Stage B vendor keys; copy from .env.example)"
fi

has_vendor_key=0
if grep -Eq '^OPENAI_API_KEY=.+' "$ENV_FILE" || grep -Eq '^GEMINI_API_KEY=.+' "$ENV_FILE"; then
  has_vendor_key=1
fi
[ "$has_vendor_key" = "1" ] || fail "Stage B requires OPENAI_API_KEY or GEMINI_API_KEY in backend/.env"

echo "== Stage A: bring up free-path stack =="
cd "$COMPOSE_DIR"
# Tier 2 E2E must not require Multilogin; host .env may set ENABLE_TIER1=true.
export ENABLE_TIER1=false
docker compose --env-file "$ENV_FILE" up --build -d api worker redis postgres social-analyzer

echo "== wait for API health =="
for i in $(seq 1 90); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health" || true)"
  [ "$code" = "200" ] && break
  sleep 3
done
[ "$code" = "200" ] || fail "API health never returned 200 (last=$code)"
pass "api health 200"

echo "== wait for social-analyzer =="
for i in $(seq 1 60); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:9005/get_settings || true)"
  [ "$code" = "200" ] && break
  sleep 5
done
[ "$code" = "200" ] || fail "social-analyzer /get_settings never returned 200 (last=$code)"
pass "social-analyzer ready"

echo "== wait for worker =="
for i in $(seq 1 30); do
  if docker compose exec -T worker true 2>/dev/null; then
    break
  fi
  sleep 2
done
docker compose exec -T worker true 2>/dev/null || fail "worker is not running (check ENABLE_TIER1 / Multilogin settings)"
pass "worker running"

echo "== worker CLIs =="
docker compose exec -T worker sh -c 'which sherlock && which maigret'
pass "worker has sherlock + maigret"

echo "== Stage A probe inside api =="
# scripts/ is dockerignored — stream the probe into the container.
docker compose exec -T api sh -c '
  set -e
  export E2E_BASE_URL=http://127.0.0.1:8000
  export SOCIAL_ANALYZER_URL=http://social-analyzer:9005
  export E2E_TIER2_LLM=0
  export E2E_BACKEND_ROOT=/app/backend
  cd /app/backend
  which sherlock
  which maigret
  mkdir -p /app/backend/.e2e-results
  python -
' < "$SCRIPT_DIR/e2e_tier2.py"
pass "Stage A Tier 2 probe"

docker compose exec -T api cat /app/backend/.e2e-results/tier2-report.json \
  > "$BACKEND_DIR/.e2e-results/tier2-report.json" || true

echo "== Stage B: litellm profile =="
docker compose --env-file "$ENV_FILE" --profile llm up -d litellm

echo "== wait for litellm =="
for i in $(seq 1 60); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:4000/v1/models 2>/dev/null || true)"
  [ "$code" = "200" ] && break
  code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:4000/health/liveliness 2>/dev/null || true)"
  [ "$code" = "200" ] && break
  sleep 3
done
[ "$code" = "200" ] || fail "litellm never became ready (last=$code)"
pass "litellm ready"

echo "== Stage B disambiguation via LiteLLM proxy =="
# scripts/ is dockerignored — pipe helper like _e2e_litellm_docker.sh
docker compose --env-file "$ENV_FILE" exec -T \
  -e LLM_MODE=litellm \
  -e LITELLM_API_BASE=http://litellm:4000 \
  -e LITELLM_MODEL="${LITELLM_MODEL:-gpt-4o-mini}" \
  -e LITELLM_FALLBACKS="${LITELLM_FALLBACKS:-gemini/gemini-2.5-flash}" \
  api sh -c '
    cd /app/backend
    export LLM_MODE=litellm
    export LITELLM_API_BASE=http://litellm:4000
    export LITELLM_FALLBACKS="${LITELLM_FALLBACKS:-gemini/gemini-2.5-flash}"
    python -c "from app.config import get_settings; get_settings.cache_clear()"
    python -
' < "$SCRIPT_DIR/_e2e_litellm_disambiguate.py"
pass "Stage B litellm disambiguation"

echo ""
echo "All Tier 2 E2E checks passed."
echo "Report: $BACKEND_DIR/.e2e-results/tier2-report.json"
