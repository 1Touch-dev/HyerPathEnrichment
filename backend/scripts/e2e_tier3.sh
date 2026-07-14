#!/usr/bin/env bash
# Tier 3 full E2E: GitRecon / theHarvester / Email Sleuth / Email Verify / CrossLinked.
#
# Stage A (free path): compose api/worker/redis/postgres/email-verifier,
# CLI prereqs, sidecar contract, isolation probes, sync + async enrich.
# Stage B (optional SMTP): set RUN_TIER3_SMTP=1 and start reacher (--profile paid).
#
# Usage:
#   bash backend/scripts/e2e_tier3.sh
#
# Windows (WSL):
#   wsl -d Ubuntu-22.04 -u root bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/e2e_tier3.sh

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

echo "== Stage A: bring up free-path stack =="
cd "$COMPOSE_DIR"
export ENABLE_TIER1=false
docker compose --env-file "$ENV_FILE" up --build -d api worker redis postgres email-verifier

echo "== wait for API health =="
for i in $(seq 1 90); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health" || true)"
  [ "$code" = "200" ] && break
  sleep 3
done
[ "$code" = "200" ] || fail "API health never returned 200 (last=$code)"
pass "api health 200"

echo "== wait for email-verifier =="
for i in $(seq 1 60); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8081/v1/health@example.com/verification" || true)"
  [ "$code" = "200" ] && break
  sleep 5
done
[ "$code" = "200" ] || fail "email-verifier never returned 200 (last=$code)"
pass "email-verifier ready"

echo "== wait for worker =="
for i in $(seq 1 30); do
  if docker compose exec -T worker true 2>/dev/null; then
    break
  fi
  sleep 2
done
docker compose exec -T worker true 2>/dev/null || fail "worker is not running (check ENABLE_TIER1 / Multilogin settings)"
pass "worker running"

echo "== worker Tier 3 CLIs =="
docker compose exec -T worker sh -c '
  which theHarvester
  which crosslinked
  which email-sleuth
  test -f "${GITRECON_SCRIPT:-/opt/gitrecon/gitrecon.py}"
'
pass "worker has Tier 3 CLIs"

echo "== Stage A probe inside api =="
docker compose exec -T api sh -c '
  set -e
  export E2E_BASE_URL=http://127.0.0.1:8000
  export EMAIL_VERIFIER_URL=http://email-verifier:8080
  export GITRECON_SCRIPT=/opt/gitrecon/gitrecon.py
  export E2E_TIER3_COMPANY=Microsoft
  export CROSSLINKED_SEARCH_ENGINES=yahoo
  export E2E_BACKEND_ROOT=/app/backend
  cd /app/backend
  mkdir -p /app/backend/.e2e-results
  python -
' < "$SCRIPT_DIR/e2e_tier3.py"
pass "Stage A Tier 3 probe"

docker compose exec -T api cat /app/backend/.e2e-results/tier3-report.json \
  > "$BACKEND_DIR/.e2e-results/tier3-report.json" || true

if [ "${RUN_TIER3_SMTP:-0}" = "1" ]; then
  echo "== Stage B: Reacher SMTP profile =="
  docker compose --env-file "$ENV_FILE" --profile paid up -d reacher
  export EMAIL_VERIFY_LEVEL=smtp
  export REACHER_URL=http://reacher:8080
  docker compose --env-file "$ENV_FILE" up -d worker api

  docker compose exec -T api sh -c '
    set -e
    export E2E_BASE_URL=http://127.0.0.1:8000
    export EMAIL_VERIFIER_URL=http://email-verifier:8080
    export GITRECON_SCRIPT=/opt/gitrecon/gitrecon.py
    export EMAIL_VERIFY_LEVEL=smtp
    export REACHER_URL=http://reacher:8080
    export RUN_TIER3_SMTP=1
    export E2E_TIER3_COMPANY=Microsoft
  export CROSSLINKED_SEARCH_ENGINES=yahoo
  export E2E_BACKEND_ROOT=/app/backend
    cd /app/backend
    python -
  ' < "$SCRIPT_DIR/e2e_tier3.py"
  pass "Stage B Reacher SMTP probe"
else
  warn "Stage B skipped (set RUN_TIER3_SMTP=1 to enable Reacher SMTP checks)"
fi

echo ""
echo "All Tier 3 E2E checks passed."
echo "Report: $BACKEND_DIR/.e2e-results/tier3-report.json"
