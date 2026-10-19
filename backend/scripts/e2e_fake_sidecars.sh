#!/usr/bin/env bash
# CI-safe fake sidecar E2E: compose override + deterministic integration probe.
#
# Verifies:
#   1. Fake sidecar containers healthy
#   2. api/worker reach sidecars on Docker network
#   3. Sidecar enrichers return fixture data
#   4. Async tier4 job includes Google Maps Scraper business data
#
# Usage:
#   bash backend/scripts/e2e_fake_sidecars.sh
#
# Requires: docker + docker compose (WSL2/Linux recommended).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Override when the api container's published host port is remapped (e.g. via
# a local docker-compose.override.yml to avoid colliding with another compose
# project already bound to :8000 on the same Docker host).
BASE="${E2E_BASE_URL:-http://localhost:8000}"
COMPOSE_FILES=(--profile paid -f docker-compose.yml -f docker-compose.fake-sidecars.yml)

cd "$COMPOSE_DIR"

# shellcheck source=_e2e_common.sh
source "$SCRIPT_DIR/_e2e_common.sh"
e2e_export_compose_defaults

# `docker compose` only auto-merges docker-compose.override.yml when no -f flag
# is given; this script passes explicit -f flags above, so re-add it manually
# if present (e.g. a local port-remap override to avoid colliding with another
# compose project already bound to the same host ports).
if [ -f "$COMPOSE_DIR/docker-compose.override.yml" ]; then
  COMPOSE_FILES+=(-f docker-compose.override.yml)
fi

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1" >&2; exit 1; }

mkdir -p "$BACKEND_DIR/.e2e-results"

cleanup() {
  if [ "${E2E_KEEP_STACK:-0}" != "1" ]; then
    docker compose "${COMPOSE_FILES[@]}" down
  fi
}
trap cleanup EXIT

echo "== bringing up fake-sidecar stack =="
export ENABLE_TIER1=false
docker compose "${COMPOSE_FILES[@]}" up --build -d \
  api worker redis postgres social-analyzer google-maps-scraper email-verifier reacher

echo "== waiting for API health =="
if ! e2e_wait_for_health "$BASE" "${COMPOSE_FILES[@]}"; then
  fail "health never returned 200 (last=${E2E_LAST_HEALTH_CODE:-000})"
fi
pass "health 200"

echo "== seed verified staff user =="
e2e_seed_verified_staff "${COMPOSE_FILES[@]}"
pass "verified staff user ready"

echo "== worker reachability to sidecars =="
docker compose "${COMPOSE_FILES[@]}" exec -T worker sh -c '
  set -e
  python -c "import urllib.request; urllib.request.urlopen(\"http://social-analyzer:9005/health\")"
  python -c "import urllib.request; urllib.request.urlopen(\"http://google-maps-scraper:8080/health\")"
  python -c "import urllib.request; urllib.request.urlopen(\"http://email-verifier:8080/v1/health@example.com/verification\")"
  python -c "import urllib.request; urllib.request.urlopen(\"http://reacher:8080/health\")"
'
pass "worker can reach all fake sidecars"

echo "== fake sidecar probe inside api =="
docker compose "${COMPOSE_FILES[@]}" exec -T \
  -e E2E_USER_EMAIL="$E2E_USER_EMAIL" \
  -e E2E_USER_PASSWORD="$E2E_USER_PASSWORD" \
  api sh -c '
  set -e
  export E2E_BASE_URL=http://127.0.0.1:8000
  export E2E_BACKEND_ROOT=/app/backend
  cd /app/backend
  mkdir -p /app/backend/.e2e-results
  python -
' < "$SCRIPT_DIR/e2e_fake_sidecars.py"
pass "fake sidecar probe"

docker compose "${COMPOSE_FILES[@]}" exec -T api cat /app/backend/.e2e-results/fake-sidecars-report.json \
  > "$BACKEND_DIR/.e2e-results/fake-sidecars-report.json" || true

echo ""
echo "All fake sidecar E2E checks passed."
