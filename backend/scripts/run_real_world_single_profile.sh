#!/usr/bin/env bash
# Real-world single-profile Tier 1-4 run on a REAL Linux host: brings up the
# supported Linux MLX compose family and runs ONE real profile (Nithin Kamath,
# CEO, Zerodha) through the live API+worker path — not the 20-profile canary
# set.
#
# Usage:
#   bash backend/scripts/run_real_world_single_profile.sh
#
# Do not use this script on Windows/WSL to claim a Linux MLX proof run.
# It is only honest on a real Linux host where `--with-linux-mlx` is supported.
#
# Env:
#   E2E_KEEP_STACK=1   leave the production stack up after the run
#
# Report: backend/.e2e-results/real-world-single-profile-report.json

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_DIR="$BACKEND_DIR/docker"
ENV_FILE="${API_ENV_FILE:-$BACKEND_DIR/.env.production}"
RESULTS_DIR="$BACKEND_DIR/.e2e-results"
BASE="http://localhost:8000"
COMPOSE_FILES=(
  -f docker-compose.yml
  -f docker-compose.prod.yml
  -f docker-compose.foundation.yml
  -f docker-compose.tier-workers.yml
  -f docker-compose.multilogin.yml
)

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1" >&2; exit 1; }
warn() { echo "WARN  $1"; }

mkdir -p "$RESULTS_DIR"

if [ ! -f "$ENV_FILE" ]; then
  fail "$ENV_FILE not found - create backend/.env.production before a production run"
fi

if [ -f /proc/version ] && grep -qi microsoft /proc/version 2>/dev/null; then
  fail "run_real_world_single_profile.sh must run on a real Linux host, not Windows/WSL"
fi

cleanup() {
  if [ "${E2E_KEEP_STACK:-0}" != "1" ]; then
    (cd "$COMPOSE_DIR" && docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" down)
  fi
}
trap cleanup EXIT

echo "== bring up supported Linux MLX production stack =="
bash "$SCRIPT_DIR/start_production.sh" --with-linux-mlx

# docker-compose.prod.yml sets `ports: []` on the sidecars (internal-only, by
# design for production) — check their health from inside the compose network
# (via the api container) instead of curling host ports.
exec_in_api() {
  (cd "$COMPOSE_DIR" && docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" exec -T api sh -c "$1")
}

echo "== wait for social-analyzer =="
for i in $(seq 1 60); do
  exec_in_api 'curl -fsS -o /dev/null http://social-analyzer:9005/get_settings' 2>/dev/null && ok=1 && break
  sleep 5
done
[ "${ok:-0}" = "1" ] || fail "social-analyzer /get_settings never became reachable"
pass "social-analyzer ready"
unset ok

echo "== wait for google-maps-scraper =="
for i in $(seq 1 30); do
  exec_in_api 'curl -fsS -o /dev/null http://google-maps-scraper:8080/api/docs' 2>/dev/null && ok=1 && break
  sleep 3
done
[ "${ok:-0}" = "1" ] || fail "gmaps /api/docs never became reachable"
pass "google-maps-scraper ready"
unset ok

echo "== wait for email-verifier =="
for i in $(seq 1 60); do
  exec_in_api 'curl -fsS -o /dev/null "http://email-verifier:8080/v1/health@example.com/verification"' 2>/dev/null && ok=1 && break
  sleep 5
done
[ "${ok:-0}" = "1" ] || fail "email-verifier never became reachable"
pass "email-verifier ready"
unset ok

echo "== wait for worker-tier1 =="
for i in $(seq 1 30); do
  if (cd "$COMPOSE_DIR" && docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" exec -T worker-tier1 true 2>/dev/null); then
    break
  fi
  sleep 2
done
(cd "$COMPOSE_DIR" && docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" exec -T worker-tier1 true 2>/dev/null) \
  || fail "worker-tier1 is not running (check Linux MLX settings)"
pass "worker-tier1 running"

echo ""
echo "========== Real-world single-profile run (Nithin Kamath / Zerodha) =========="

# The WSL host has no python3-venv/pip (and no interactive sudo in this
# session) — run the client script inside the `api` container instead, which
# already has httpx + the full app package installed. The job itself is
# still dispatched to the real worker set (`worker`, `worker-tier234`,
# `worker-tier1`, `worker-email`, `worker-job-matching`) via Redis/RQ; only
# the POST/poll client runs inside `api`. scripts/ is
# dockerignored, so stream the file in via stdin (same pattern as
# e2e_realworld_strict.sh).
PROD_API_TOKEN="$(grep -E '^API_TOKEN=' "$ENV_FILE" | head -n1 | cut -d= -f2-)"

RUN_EXIT=0
(cd "$COMPOSE_DIR" && docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" exec -T api sh -c '
  set -e
  export E2E_BACKEND_ROOT=/app/backend
  export E2E_BASE_URL=http://127.0.0.1:8000
  export API_TOKEN='"'$PROD_API_TOKEN'"'
  cd /app/backend
  mkdir -p /app/backend/.e2e-results
  python - --json
' < "$SCRIPT_DIR/run_real_world_single_profile.py") || RUN_EXIT=$?

(cd "$COMPOSE_DIR" && docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" exec -T api \
  cat /app/backend/.e2e-results/real-world-single-profile-report.json) \
  > "$RESULTS_DIR/real-world-single-profile-report.json" 2>/dev/null || true

if [ "$RUN_EXIT" -eq 0 ]; then
  pass "real-world single-profile run"
else
  warn "real-world single-profile run FAILED (exit=$RUN_EXIT)"
fi

echo ""
echo "Report: $RESULTS_DIR/real-world-single-profile-report.json"
exit "$RUN_EXIT"
