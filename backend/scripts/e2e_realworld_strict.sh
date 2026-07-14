#!/usr/bin/env bash
# Strict real-world E2E: brings up compose + sidecars, runs probe inside api container.
#
# Run from repo root or anywhere:
#   bash backend/scripts/e2e_realworld_strict.sh
#
# Requires Docker in WSL (Ubuntu). On Windows, invoke via:
#   wsl -d Ubuntu -u root bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/e2e_realworld_strict.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$BACKEND_DIR/.env"
BASE="http://localhost:8000"

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1" >&2; exit 1; }
warn() { echo "WARN  $1"; }

mkdir -p "$BACKEND_DIR/.e2e-results"
service docker start >/dev/null 2>&1 || true

if [ ! -f "$ENV_FILE" ]; then
  cp "$BACKEND_DIR/.env.example" "$ENV_FILE"
  warn "created $ENV_FILE from .env.example"
fi

echo "== bring up api, worker, redis, postgres, sidecars =="
cd "$COMPOSE_DIR"
export ENABLE_TIER1=false
docker compose --env-file "$ENV_FILE" build api worker
docker compose --env-file "$ENV_FILE" up -d api worker redis postgres social-analyzer google-maps-scraper

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

echo "== wait for google-maps-scraper =="
for i in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/api/docs || true)"
  [ "$code" = "200" ] && break
  sleep 3
done
[ "$code" = "200" ] || fail "gmaps /api/docs never returned 200 (last=$code)"
pass "google-maps-scraper ready"

echo "== run strict probe (inside api container — Python 3.12) =="
# scripts/ is dockerignored — stream the probe into the container.
docker compose --env-file "$ENV_FILE" exec -T api sh -c '
  set -e
  export E2E_BASE_URL=http://127.0.0.1:8000
  export SOCIAL_ANALYZER_URL=http://social-analyzer:9005
  export GMAPS_SCRAPER_URL=http://google-maps-scraper:8080
  export GITRECON_SCRIPT=/opt/gitrecon/gitrecon.py
  export GMAPS_JOB_TIMEOUT_SECONDS='"${GMAPS_JOB_TIMEOUT_SECONDS:-300}"'
  export GMAPS_JOB_POLL_SECONDS='"${GMAPS_JOB_POLL_SECONDS:-10}"'
  export E2E_BACKEND_ROOT=/app/backend
  cd /app/backend
  mkdir -p /app/backend/.e2e-results
  test -f "${GITRECON_SCRIPT}"
  python -
' < "$SCRIPT_DIR/e2e_realworld_strict.py"
pass "strict real-world E2E probe"

docker compose exec -T api cat /app/backend/.e2e-results/strict-report.json \
  > "$BACKEND_DIR/.e2e-results/strict-report.json" || true

echo ""
echo "All strict real-world E2E checks passed."
echo "Report: $BACKEND_DIR/.e2e-results/strict-report.json"
