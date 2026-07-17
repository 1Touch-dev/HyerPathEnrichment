#!/usr/bin/env bash
# Scrapoxy staging proof (Task 62).
#
# Verifies PROXY_MODE=scrapoxy wiring: Scrapoxy container up, ProxyProvider
# returns endpoint, unit tests pass. Live enricher OK is best-effort (needs
# proxy fleet configured in Scrapoxy commander).
#
# Usage:
#   bash backend/scripts/e2e_scrapoxy.sh
#
# Env (backend/.env):
#   PROXY_MODE=scrapoxy
#   SCRAPOXY_URL=http://scrapoxy:8888
#   SCRAPOXY_USERNAME / SCRAPOXY_PASSWORD (optional)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$BACKEND_DIR/.env"
REPORT="$BACKEND_DIR/.e2e-results/scrapoxy-report.json"

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1" >&2; exit 1; }
warn() { echo "WARN  $1"; }

mkdir -p "$BACKEND_DIR/.e2e-results"
service docker start >/dev/null 2>&1 || true

if [ ! -f "$ENV_FILE" ]; then
  cp "$BACKEND_DIR/.env.example" "$ENV_FILE"
  warn "created $ENV_FILE from .env.example"
fi

export ENABLE_TIER1=false
export PROXY_MODE=scrapoxy
export SCRAPOXY_URL="${SCRAPOXY_URL:-http://scrapoxy:8888}"

echo "== bring up staging stack + scrapoxy =="
cd "$COMPOSE_DIR"
docker compose \
  --env-file "$ENV_FILE" \
  -f docker-compose.yml \
  -f docker-compose.staging.yml \
  --profile paid \
  up -d --build api worker redis postgres scrapoxy

echo "== wait for scrapoxy commander =="
scrapoxy_ok=0
for i in $(seq 1 40); do
  cid="$(docker compose -f docker-compose.yml -f docker-compose.staging.yml ps -q scrapoxy 2>/dev/null || true)"
  if [ -n "$cid" ] && [ "$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null || echo false)" = "true" ]; then
    if docker compose -f docker-compose.yml -f docker-compose.staging.yml exec -T scrapoxy \
      wget -q -O /dev/null http://localhost:8890 2>/dev/null; then
      scrapoxy_ok=1
      break
    fi
  fi
  sleep 3
done
[ "$scrapoxy_ok" = "1" ] || fail "scrapoxy not running or commander :8890 not ready"
pass "scrapoxy container up"

echo "== ProxyProvider endpoint inside worker =="
proxy_out="$(docker compose -f docker-compose.yml -f docker-compose.staging.yml exec -T worker \
  python -c "from app.clients.proxy import ProxyProvider; print(ProxyProvider().get() or '')")"
if [ -z "$proxy_out" ]; then
  fail "ProxyProvider.get() returned empty with PROXY_MODE=scrapoxy"
fi
echo "  proxy=$proxy_out"
pass "ProxyProvider returns scrapoxy URL"

echo "== unit test regression =="
docker compose -f docker-compose.yml -f docker-compose.staging.yml exec -T worker \
  python -m pytest tests/test_enrichers.py -k scrapoxy -v --tb=short
pass "pytest scrapoxy unit tests"

echo "== optional live probe (sherlock via proxy) =="
probe_status="SKIP"
if docker compose -f docker-compose.yml -f docker-compose.staging.yml exec -T worker \
  python scripts/probe_enrichers.py --only sherlock --json 2>/dev/null | grep -q '"status"'; then
  probe_status="RAN"
  warn "sherlock probe executed — EMPTY is OK without Scrapoxy proxy fleet; wiring is proven above"
fi

python3 - <<PY
import json, time
from pathlib import Path
report = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "proxy_endpoint": """$proxy_out""",
    "probe_status": """$probe_status""",
    "exit_code": 0,
}
Path("""$REPORT""").write_text(json.dumps(report, indent=2))
print(f"Report written to $REPORT")
PY

pass "scrapoxy staging proof complete"
