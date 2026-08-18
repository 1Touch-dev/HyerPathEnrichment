#!/usr/bin/env bash
# PROOF 3, final attempt: deterministic timing via SIGSTOP/SIGCONT+fixed-delay
# instead of a fragile Redis-status race. Both prior real timing samples
# (12.7s and 32.6s) for a "cv" document comfortably exceed a 4s buffer, so
# resuming the frozen worker and waiting 4s before SIGKILL reliably lands
# while the job is genuinely in RQ status="started" (StartedJobRegistry),
# not still queued/intermediate and not yet finished.
set -uo pipefail

REPO=/mnt/g/ThunderMarketingCorp/HyerEnrichment
BACKEND=$REPO/backend
FIXTURES=$BACKEND/tests/fixtures
BASE=http://127.0.0.1:8000
VENV=$HOME/hyre-e2e-venv
COOKIES=$(mktemp)
WORKER_PID_FILE=$HOME/hyre-e2e-worker.pid

echo "=== loading backend/.env.production for POSTGRES_USER/PASSWORD (values never echoed) ==="
ENV_PROD_CLEAN=$(mktemp)
tr -d '\r' < "$BACKEND/.env.production" > "$ENV_PROD_CLEAN"
set -a
source "$ENV_PROD_CLEAN"
set +a
rm -f "$ENV_PROD_CLEAN"
export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5433/hyrepath"
export REDIS_URL="redis://localhost:6379/0"
export EMAIL_ENABLED=false
export EMAIL_TEST_MODE=true
export FRONTEND_URL=http://localhost:3000
export APP_ENV=e2e-test

pyjson() {
  python3 -c "
import sys, json
d = json.load(sys.stdin)
path = sys.argv[1].split('.')
for p in path:
    d = d[p]
print(d)
" "$1"
}

echo ""
echo "############################################"
echo "## Register + verify + login a NEW test user (final proof-3 attempt)"
echo "############################################"
EMAIL="e2e-doc-fix-crash3-$(date +%s)@example.com"
PASSWORD="TestPass123!"
echo "email=$EMAIL"
curl -s -X POST "$BASE/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"first_name\":\"E2E\",\"last_name\":\"Crash3\"}"
echo
VER_TOKEN=$(docker exec docker-postgres-1 psql -U hyrepath -d hyrepath -tAc \
  "SELECT t.token FROM email_verification_tokens t JOIN users u ON u.id = t.user_id WHERE u.email='$EMAIL';" 2>&1 | tr -d '[:space:]')
echo "verification_token(len)=${#VER_TOKEN}"
curl -s -X POST "$BASE/auth/verify-email" -H 'Content-Type: application/json' -d "{\"token\":\"$VER_TOKEN\"}"
echo
curl -s -c "$COOKIES" -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
echo

echo ""
echo "############################################"
echo "## PROOF 3 (final): worker crash after job reaches 'started'"
echo "############################################"
echo "--- clean slate: kill any existing worker ---"
pkill -9 -f "rq worker document_processing" || true
sleep 1

echo "--- starting the 'live' worker (correctly configured) ---"
nohup "$VENV/bin/rq" worker document_processing --url redis://localhost:6379/0 \
  > "$HOME/hyre-e2e-worker-live3.log" 2>&1 &
LIVE_PID=$!
echo "$LIVE_PID" > "$WORKER_PID_FILE"
echo "live worker pid=$LIVE_PID"
sleep 1
ps -p "$LIVE_PID" -o pid,stat,cmd --no-headers

echo "--- SIGSTOP the worker (freeze it so it cannot dequeue) ---"
kill -STOP "$LIVE_PID"
sleep 1
ps -p "$LIVE_PID" -o pid,stat,cmd --no-headers

echo "--- uploading a valid PDF while worker is frozen (document_type=cv) ---"
RESP3=$(curl -s -b "$COOKIES" -c "$COOKIES" -X POST "$BASE/api/documents/upload?document_type=cv" \
  -F "file=@$FIXTURES/test_cv_v2.pdf;type=application/pdf")
echo "upload response: $RESP3"
JOB3=$(echo "$RESP3" | pyjson data.job_id)
DOC3=$(echo "$RESP3" | pyjson data.document_id)
echo "job_id=$JOB3 document_id=$DOC3"

echo "--- confirm job is still 'pending' while worker frozen ---"
curl -s -b "$COOKIES" "$BASE/api/documents/jobs/$JOB3"
echo

echo "--- resume worker, wait 4s for it to reach RQ status=started, THEN SIGKILL ---"
date +"resume at %Y-%m-%dT%H:%M:%S.%N"
kill -CONT "$LIVE_PID"
sleep 4
date +"kill at %Y-%m-%dT%H:%M:%S.%N"
pkill -9 -f "rq worker document_processing"
sleep 1
echo "--- process list after kill (should show none) ---"
ps aux | grep -E "rq worker" | grep -v grep || echo "(no rq worker processes running)"
echo "--- worker-live3 log (should show 'Processing document'/dequeue line, no completion line) ---"
tail -n 20 "$HOME/hyre-e2e-worker-live3.log"

echo "--- immediate job status right after kill (expect still non-terminal) ---"
curl -s -b "$COOKIES" "$BASE/api/documents/jobs/$JOB3"
echo

echo "--- waiting for StartedJobRegistry heartbeat TTL to expire (~90s from job start per rq 2.10 formula) ---"
for i in $(seq 1 22); do
  echo "  waiting... $((i*5))s elapsed"
  sleep 5
done

echo "--- starting a FRESH rq worker process (new PID), correctly configured ---"
nohup "$VENV/bin/rq" worker document_processing --url redis://localhost:6379/0 \
  > "$HOME/hyre-e2e-worker-fresh3.log" 2>&1 &
NEW_WORKER_PID=$!
echo "$NEW_WORKER_PID" > "$WORKER_PID_FILE"
echo "new worker pid=$NEW_WORKER_PID"
sleep 3
echo "--- new worker startup log ---"
cat "$HOME/hyre-e2e-worker-fresh3.log"

echo "--- polling GET /api/documents/jobs/$JOB3 until terminal ---"
STATUS3="pending"
for i in $(seq 1 30); do
  R=$(curl -s -b "$COOKIES" "$BASE/api/documents/jobs/$JOB3")
  STATUS3=$(echo "$R" | pyjson data.status)
  echo "  [$i] status=$STATUS3 raw=$R"
  if [ "$STATUS3" = "completed" ] || [ "$STATUS3" = "failed" ]; then
    break
  fi
  sleep 5
done
echo ">>> PROOF 3 (final) status: $STATUS3"
echo "--- tail of fresh worker log after polling ---"
tail -n 60 "$HOME/hyre-e2e-worker-fresh3.log"

echo ""
echo "############################################"
echo "## PROOF 3 FINAL SUMMARY"
echo "############################################"
echo "job_id=$JOB3 document_id=$DOC3 final_status=$STATUS3"
