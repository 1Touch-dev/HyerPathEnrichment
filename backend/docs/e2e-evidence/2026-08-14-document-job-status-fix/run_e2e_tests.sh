#!/usr/bin/env bash
# Chunk 4 e2e proof runs against the real stack started by setup_stack.sh.
# Three proof points: (1) success path, (2) in-task failure path,
# (3) worker-crash / abandoned-job path. See README.md for narrative.
set -uo pipefail

REPO=/mnt/g/ThunderMarketingCorp/HyerEnrichment
BACKEND=$REPO/backend
FIXTURES=$BACKEND/tests/fixtures
BASE=http://127.0.0.1:8000
VENV=$HOME/hyre-e2e-venv
COOKIES=$(mktemp)
WORKER_LOG=$HOME/hyre-e2e-worker.log
WORKER_PID_FILE=$HOME/hyre-e2e-worker.pid

pyjson() {
  # reads JSON on stdin, prints the dotted path (e.g. data.job_id)
  python3 -c "
import sys, json
d = json.load(sys.stdin)
path = sys.argv[1].split('.')
for p in path:
    d = d[p]
print(d)
" "$1"
}

echo "############################################"
echo "## Register + verify + login a test user  ##"
echo "############################################"
EMAIL="e2e-doc-fix-$(date +%s)@example.com"
PASSWORD="TestPass123!"
echo "email=$EMAIL"

echo "--- POST /auth/register ---"
curl -s -X POST "$BASE/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"first_name\":\"E2E\",\"last_name\":\"DocFix\"}"
echo

echo "--- fetching verification token directly from Postgres (EMAIL_TEST_MODE=true; no real email sent) ---"
# The real token lives in email_verification_tokens (joined by user_id), not
# users.verification_token (that column is unused by the current verification flow).
VER_TOKEN=$(docker exec docker-postgres-1 psql -U hyrepath -d hyrepath -tAc \
  "SELECT t.token FROM email_verification_tokens t JOIN users u ON u.id = t.user_id WHERE u.email='$EMAIL';" 2>&1 | tr -d '[:space:]')
echo "verification_token(len)=${#VER_TOKEN}"

echo "--- POST /auth/verify-email ---"
curl -s -X POST "$BASE/auth/verify-email" -H 'Content-Type: application/json' \
  -d "{\"token\":\"$VER_TOKEN\"}"
echo

echo "--- POST /auth/login (stores HttpOnly cookies) ---"
curl -s -c "$COOKIES" -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
echo

echo "--- GET /auth/me (confirm is_verified=true) ---"
curl -s -b "$COOKIES" "$BASE/auth/me"
echo

echo ""
echo "############################################"
echo "## PROOF 1: success path (real, valid PDF)##"
echo "############################################"
RESP1=$(curl -s -b "$COOKIES" -c "$COOKIES" -X POST "$BASE/api/documents/upload?document_type=cv" \
  -F "file=@$FIXTURES/sample_cv.pdf;type=application/pdf")
echo "upload response: $RESP1"
JOB1=$(echo "$RESP1" | pyjson data.job_id)
DOC1=$(echo "$RESP1" | pyjson data.document_id)
echo "job_id=$JOB1 document_id=$DOC1"

echo "--- polling GET /api/documents/jobs/$JOB1 until terminal ---"
STATUS1="pending"
for i in $(seq 1 60); do
  R=$(curl -s -b "$COOKIES" "$BASE/api/documents/jobs/$JOB1")
  STATUS1=$(echo "$R" | pyjson data.status)
  echo "  [$i] status=$STATUS1 raw=$R"
  if [ "$STATUS1" = "completed" ] || [ "$STATUS1" = "failed" ]; then
    break
  fi
  sleep 1
done
echo ">>> PROOF 1 final status: $STATUS1"

echo ""
echo "############################################"
echo "## PROOF 2: in-task failure path (malformed.pdf)"
echo "############################################"
echo "--- malformed.pdf fixture bytes (hex) ---"
xxd "$FIXTURES/malformed.pdf" || od -An -tx1 "$FIXTURES/malformed.pdf"
RESP2=$(curl -s -b "$COOKIES" -c "$COOKIES" -X POST "$BASE/api/documents/upload?document_type=cv" \
  -F "file=@$FIXTURES/malformed.pdf;type=application/pdf")
echo "upload response: $RESP2"
JOB2=$(echo "$RESP2" | pyjson data.job_id)
DOC2=$(echo "$RESP2" | pyjson data.document_id)
echo "job_id=$JOB2 document_id=$DOC2"

echo "--- polling GET /api/documents/jobs/$JOB2 until terminal ---"
STATUS2="pending"
for i in $(seq 1 60); do
  R=$(curl -s -b "$COOKIES" "$BASE/api/documents/jobs/$JOB2")
  STATUS2=$(echo "$R" | pyjson data.status)
  echo "  [$i] status=$STATUS2 raw=$R"
  if [ "$STATUS2" = "completed" ] || [ "$STATUS2" = "failed" ]; then
    break
  fi
  sleep 1
done
echo ">>> PROOF 2 final status: $STATUS2"

echo ""
echo "############################################"
echo "## PROOF 3: worker crash / abandoned-job path"
echo "############################################"
CURRENT_WORKER_PID=$(cat "$WORKER_PID_FILE")
echo "current worker pid: $CURRENT_WORKER_PID"
ps -p "$CURRENT_WORKER_PID" -o pid,stat,cmd --no-headers || echo "worker not found under that pid"

echo "--- SIGSTOP the worker (freeze it so it cannot dequeue) ---"
kill -STOP "$CURRENT_WORKER_PID"
sleep 1
ps -p "$CURRENT_WORKER_PID" -o pid,stat,cmd --no-headers

echo "--- upload a valid PDF while worker is frozen ---"
RESP3=$(curl -s -b "$COOKIES" -c "$COOKIES" -X POST "$BASE/api/documents/upload?document_type=cv" \
  -F "file=@$FIXTURES/test_cv_v2.pdf;type=application/pdf")
echo "upload response: $RESP3"
JOB3=$(echo "$RESP3" | pyjson data.job_id)
DOC3=$(echo "$RESP3" | pyjson data.document_id)
echo "job_id=$JOB3 document_id=$DOC3"

echo "--- confirm job is still 'pending' while worker frozen (proves it has NOT been picked up yet) ---"
curl -s -b "$COOKIES" "$BASE/api/documents/jobs/$JOB3"
echo

echo "--- resume worker, then immediately SIGKILL worker + any forked work-horse (no sleep between) ---"
date +"resume+kill at %Y-%m-%dT%H:%M:%S.%N"
kill -CONT "$CURRENT_WORKER_PID"
pkill -9 -f "rq worker document_processing"
date +"kill issued at %Y-%m-%dT%H:%M:%S.%N"
sleep 1
echo "--- process list after kill (should show none) ---"
ps aux | grep -E "rq worker" | grep -v grep || echo "(no rq worker processes running)"

echo "--- immediate job status right after kill ---"
curl -s -b "$COOKIES" "$BASE/api/documents/jobs/$JOB3"
echo

echo "--- checking the RQ job's own Redis-side status (proves whether it reached STARTED before the kill) ---"
redis-cli --scan --pattern 'rq:job:*' | while read -r k; do
  data=$(redis-cli HGET "$k" data 2>/dev/null | grep -a "$DOC3" || true)
  if [ -n "$data" ]; then
    echo "matched key: $k"
    redis-cli HGETALL "$k"
  fi
done

echo "--- waiting for StartedJobRegistry heartbeat TTL to expire (rq 2.10: min(job_timeout,30)+60 ~= 90s from job start) ---"
for i in $(seq 1 24); do
  echo "  waiting... $((i*5))s elapsed"
  sleep 5
done

echo "--- starting a FRESH rq worker process (new PID) ---"
nohup "$VENV/bin/rq" worker document_processing --url redis://localhost:6379/0 \
  > "$HOME/hyre-e2e-worker2.log" 2>&1 &
NEW_WORKER_PID=$!
echo "$NEW_WORKER_PID" > "$HOME/hyre-e2e-worker2.pid"
echo "new worker pid=$NEW_WORKER_PID"
sleep 3
echo "--- new worker startup log (first lines, should show maintenance/cleanup activity) ---"
head -n 40 "$HOME/hyre-e2e-worker2.log"

echo "--- polling GET /api/documents/jobs/$JOB3 until terminal (fresh worker's maintenance pass should fire on_failure) ---"
STATUS3="pending"
for i in $(seq 1 40); do
  R=$(curl -s -b "$COOKIES" "$BASE/api/documents/jobs/$JOB3")
  STATUS3=$(echo "$R" | pyjson data.status)
  echo "  [$i] status=$STATUS3 raw=$R"
  if [ "$STATUS3" = "completed" ] || [ "$STATUS3" = "failed" ]; then
    break
  fi
  sleep 5
done
echo ">>> PROOF 3 final status: $STATUS3"

echo ""
echo "############################################"
echo "## SUMMARY"
echo "############################################"
echo "PROOF1 (success path)          job_id=$JOB1 final_status=$STATUS1"
echo "PROOF2 (in-task failure path)  job_id=$JOB2 final_status=$STATUS2"
echo "PROOF3 (worker crash path)     job_id=$JOB3 final_status=$STATUS3"
