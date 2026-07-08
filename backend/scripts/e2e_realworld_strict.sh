#!/usr/bin/env bash
# Strict real-world E2E: brings up compose + sidecars, installs gitrecon, runs probe.
#
# Run from repo root or anywhere:
#   bash backend/scripts/e2e_realworld_strict.sh
#
# Requires Docker in WSL (Ubuntu). On Windows, invoke via:
#   wsl -d Ubuntu-22.04 -u root bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/e2e_realworld_strict.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BASE="http://localhost:8000"

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1" >&2; exit 1; }

service docker start >/dev/null 2>&1 || true

echo "== install gitrecon (if missing) =="
GITRECON_DIR="/opt/gitrecon"
if [ ! -f "$GITRECON_DIR/gitrecon.py" ]; then
  rm -rf "$GITRECON_DIR"
  git clone --depth 1 https://github.com/GONZOsint/gitrecon.git "$GITRECON_DIR"
  pip3 install -q -r "$GITRECON_DIR/requirements.txt" rich requests
fi
export GITRECON_SCRIPT="$GITRECON_DIR/gitrecon.py"

echo "== bring up api, worker, redis, postgres, sidecars =="
cd "$COMPOSE_DIR"
docker compose up --build -d api worker redis postgres social-analyzer google-maps-scraper

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
cd "$COMPOSE_DIR"
docker compose exec -T api sh -c '
  set -e
  apt-get update -qq && apt-get install -y -qq git >/dev/null
  if [ ! -f /tmp/gitrecon/gitrecon.py ]; then
    git clone --depth 1 https://github.com/GONZOsint/gitrecon.git /tmp/gitrecon
    pip install -q -r /tmp/gitrecon/requirements.txt rich requests
  fi
  export E2E_BASE_URL=http://127.0.0.1:8000
  export SOCIAL_ANALYZER_URL=http://social-analyzer:9005
  export GMAPS_SCRAPER_URL=http://google-maps-scraper:8080
  export GITRECON_SCRIPT=/tmp/gitrecon/gitrecon.py
  export GMAPS_JOB_TIMEOUT_SECONDS='"${GMAPS_JOB_TIMEOUT_SECONDS:-300}"'
  export GMAPS_JOB_POLL_SECONDS='"${GMAPS_JOB_POLL_SECONDS:-10}"'
  cd /app/backend
  python scripts/e2e_realworld_strict.py
'
pass "strict real-world E2E probe"
