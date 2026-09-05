#!/usr/bin/env bash
# Module 3 (Interview Prep & Sentiment Analysis) local smoke test.
#
# Unlike the pytest suite (TestClient + dependency overrides), this brings up a
# REAL uvicorn process + REAL RQ worker against a REAL Redis instance and a
# throwaway SQLite database, then drives the full user journey over real HTTP:
#   register -> verify -> login -> create session -> fetch questions ->
#   submit attempt -> poll for RQ-worker-generated feedback -> upload audio ->
#   poll for transcription status.
#
# Runs with no OpenAI/Hume keys by default (the fail-soft path — see
# backend/docs/MODULE3_REALWORLD_TESTING.md to re-run this against real keys).
#
# Usage (from repo root or anywhere):
#   bash backend/scripts/smoke_test_module3.sh
#
# Requires: a reachable Redis instance (defaults to localhost:6379, uses db 2
# so it never collides with dev data on db 0). Does NOT require Docker.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PY="$BACKEND_DIR/.venv/bin/python"

SMOKE_DB="${SMOKE_DB_PATH:-/tmp/hyrepath-smoke-$$.db}"
SMOKE_REDIS_URL="${SMOKE_REDIS_URL:-redis://localhost:6379/2}"
SMOKE_PORT="${SMOKE_PORT:-8010}"
UVICORN_LOG="$(mktemp /tmp/hyrepath-smoke-uvicorn.XXXXXX.log)"
WORKER_LOG="$(mktemp /tmp/hyrepath-smoke-worker.XXXXXX.log)"
MIGRATE_LOG="$(mktemp /tmp/hyrepath-smoke-migrate.XXXXXX.log)"

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1" >&2; exit 1; }

UVICORN_PID=""
WORKER_PID=""
cleanup() {
  [ -n "$UVICORN_PID" ] && kill "$UVICORN_PID" 2>/dev/null || true
  [ -n "$WORKER_PID" ] && kill "$WORKER_PID" 2>/dev/null || true
  rm -f "$SMOKE_DB" "$SMOKE_DB-shm" "$SMOKE_DB-wal" "$UVICORN_LOG" "$WORKER_LOG" "$MIGRATE_LOG"
}
trap cleanup EXIT

cd "$BACKEND_DIR"

export DATABASE_URL="sqlite+aiosqlite:///${SMOKE_DB}"
export REDIS_URL="$SMOKE_REDIS_URL"
export EMAIL_ENABLED=false
export EMAIL_TEST_MODE=true
export OPENAI_API_KEY=""
export HUME_API_KEY=""

echo "== checking Redis reachability =="
redis-cli -u "$SMOKE_REDIS_URL" ping | grep -q PONG || fail "Redis not reachable at $SMOKE_REDIS_URL"
pass "Redis reachable"

echo "== running migrations against fresh SQLite db =="
"$VENV_PY" -m alembic upgrade head > "$MIGRATE_LOG" 2>&1 \
  || fail "alembic upgrade head failed - see $MIGRATE_LOG"
pass "alembic upgrade head"

echo "== seeding a minimal offline question-bank fixture (no LLM calls) =="
"$VENV_PY" scripts/seed_questions_minimal_offline.py || fail "question fixture seed failed"
pass "question bank fixture seeded"

echo "== starting uvicorn on :$SMOKE_PORT =="
"$VENV_PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$SMOKE_PORT" > "$UVICORN_LOG" 2>&1 &
UVICORN_PID=$!
for i in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$SMOKE_PORT/health" || true)"
  [ "$code" = "200" ] && break
  sleep 1
done
[ "$code" = "200" ] || fail "uvicorn health never returned 200 (last=$code) - see $UVICORN_LOG"
pass "uvicorn health 200"

echo "== starting RQ worker =="
"$VENV_PY" -m app.workers.rq_worker > "$WORKER_LOG" 2>&1 &
WORKER_PID=$!
worker_started=0
for i in $(seq 1 20); do
  grep -q "Worker starting" "$WORKER_LOG" 2>/dev/null && { worker_started=1; break; }
  kill -0 "$WORKER_PID" 2>/dev/null || break
  sleep 1
done
[ "$worker_started" = "1" ] || fail "RQ worker did not start - see $WORKER_LOG"
pass "RQ worker started"

echo "== running full HTTP smoke test =="
BASE_URL="http://127.0.0.1:$SMOKE_PORT" \
  SMOKE_DB_PATH="$SMOKE_DB" \
  SMOKE_WORKER_LOG="$WORKER_LOG" \
  "$VENV_PY" scripts/smoke_test_module3.py
pass "full HTTP smoke test"

echo ""
echo "All Module 3 smoke test checks passed."
