#!/usr/bin/env bash
# Docker Compose end-to-end test: proves API + worker share one Postgres.
#
# Verifies the Postgres slice:
#   1. GET  /health                 -> 200
#   2. POST /enrich                  -> 202 queued
#   3. poll GET /enrich/{id}         -> completed (worker + shared DB)
#   4. POST /api/opt-out             -> enrich blocked; suppression persisted
#   5. restart worker container      -> purged job still present (data in volume)
#
# Usage (from repo root or anywhere):
#   bash backend/scripts/e2e_compose_test.sh
#
# Requires: docker + docker compose. Run inside the environment that has the
# Docker daemon (e.g. WSL2 Ubuntu). Uses the published API port on localhost.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
BASE="http://localhost:8000"
TOKEN="change-me"
AUTH="Authorization: Bearer $TOKEN"
# Unique per run so a prior opt-out on the postgres volume cannot suppress enqueue.
IDENT="compose-e2e-$(date +%s)"

cd "$COMPOSE_DIR"

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1" >&2; exit 1; }

echo "== bringing up api, worker, redis, postgres =="
docker compose up --build -d api worker redis postgres

echo "== waiting for API health =="
for i in $(seq 1 60); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health" || true)"
  [ "$code" = "200" ] && break
  sleep 2
done
[ "$code" = "200" ] || fail "health never returned 200 (last=$code)"
pass "health 200"

echo "== enqueue async job (ident=$IDENT) =="
resp="$(curl -s -X POST "$BASE/enrich" -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$IDENT\",\"requested_tiers\":[\"tier2\"]}")"
echo "  enqueue response: $resp"
status="$(echo "$resp" | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')"
job_id="$(echo "$resp" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')"
[ "$status" = "queued" ] || fail "expected queued, got $status"
pass "async enqueue queued (job_id=$job_id)"

echo "== poll until terminal =="
final=""
for i in $(seq 1 40); do
  poll="$(curl -s "$BASE/enrich/$job_id" -H "$AUTH")"
  final="$(echo "$poll" | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')"
  [ "$final" != "queued" ] && [ "$final" != "running" ] && break
  sleep 2
done
[ "$final" = "completed" ] || fail "job did not complete (last=$final)"
pass "async poll completed"

echo "== opt-out suppression =="
oc="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/opt-out" -H "$AUTH" \
  -H 'Content-Type: application/json' -d "{\"identifier\":\"$IDENT\",\"reason\":\"e2e\"}")"
[ "$oc" = "202" ] || fail "opt-out expected 202, got $oc"
chk="$(curl -s "$BASE/api/opt-out/check?identifier=$IDENT" -H "$AUTH" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["suppressed"])')"
[ "$chk" = "True" ] || fail "identifier not reported suppressed"
sup="$(curl -s -X POST "$BASE/enrich/sync" -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$IDENT\",\"requested_tiers\":[\"tier2\"]}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')"
[ "$sup" = "suppressed" ] || fail "enrich not suppressed (got $sup)"
pass "opt-out blocks enrichment (suppression in Postgres)"

echo "== opt-out purge clears prior job dossier =="
# API always serializes dossier via Dossier.model_validate, so an empty payload
# still has ~11 default keys — assert status=purged instead of len(dossier)==0.
purged_status="$(curl -s "$BASE/enrich/$job_id" -H "$AUTH" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')"
[ "$purged_status" = "purged" ] || fail "prior job not purged after opt-out (status=$purged_status)"
pass "opt-out purged stored dossier for matching identifier"

echo "== restart worker; purged job must survive in Postgres volume =="
docker compose restart worker
sleep 3
after="$(curl -s "$BASE/enrich/$job_id" -H "$AUTH" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')"
[ "$after" = "purged" ] || fail "old job lost after worker restart (got $after)"
pass "old job still purged after worker restart"

echo ""
echo "All Docker Compose E2E checks passed."
