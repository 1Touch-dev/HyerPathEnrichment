#!/usr/bin/env bash
# Host-side CD reliability tests (DB ensure, HTTP wait, deploy state).
# Does NOT run full CD, mutate production app data, or advance .deploy/current_sha
# for a real release. Safe throwaway DB names are created and dropped.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

PASS=0
FAIL=0
TMP_ROOT="$(mktemp -d)"
cleanup() {
  # Best-effort drop of throwaway DBs and temp HTTP servers.
  if [[ -n "${PG_CID:-}" && -n "${PGUSER:-}" ]]; then
    for db in ${THROWAWAY_DBS:-}; do
      docker exec "$PG_CID" psql -U "$PGUSER" -d postgres -c \
        "DROP DATABASE IF EXISTS ${db};" >/dev/null 2>&1 || true
    done
  fi
  if [[ -n "${HTTP_PIDS:-}" ]]; then
    # shellcheck disable=SC2086
    kill $HTTP_PIDS 2>/dev/null || true
  fi
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

ok() { echo "PASS  $*"; PASS=$((PASS + 1)); }
bad() { echo "FAIL  $*" >&2; FAIL=$((FAIL + 1)); }

assert_eq() {
  local label="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    ok "$label"
  else
    bad "$label (got='${got}' want='${want}')"
  fi
}

assert_rc() {
  local label="$1" want_rc="$2"
  shift 2
  set +e
  "$@" >/dev/null 2>&1
  local rc=$?
  set -e
  assert_eq "$label" "$rc" "$want_rc"
}

echo "=== CD reliability tests ==="
echo "REPO_ROOT=${REPO_ROOT}"

# ---------------------------------------------------------------------------
# 0) Reproduce root cause: docker exec -i steals stdin under scripted feed
# ---------------------------------------------------------------------------
echo
echo "--- 0) Reproduce docker exec -i stdin theft ---"
PG_CID="$(postgres_container)"
PGUSER="$(env_get POSTGRES_USER)"
PGUSER="${PGUSER:-hyrepath}"
if [[ -z "$PG_CID" ]]; then
  bad "postgres container available"
else
  ok "postgres container available"
  # Feed a fake "rest of deploy script" on stdin while using -i — mirrors SSH CD.
  set +e
  stolen="$(
    printf 'THIS_IS_NOT_SQL_FROM_THE_REST_OF_THE_SCRIPT;\n' | \
      docker exec -i "$PG_CID" psql -U "$PGUSER" -d postgres -Atc \
        "SELECT 1 FROM pg_database WHERE datname='langfuse'" 2>&1
  )"
  stolen_rc=$?
  set -e
  # Without -i, same query must succeed.
  set +e
  clean="$(docker exec "$PG_CID" psql -U "$PGUSER" -d postgres -Atc \
    "SELECT 1 FROM pg_database WHERE datname='langfuse'" 2>&1)"
  clean_rc=$?
  set -e
  if [[ "$clean_rc" -eq 0 && "$clean" == "1" ]]; then
    ok "existence check without -i returns 1 for langfuse"
  else
    bad "existence check without -i (rc=${clean_rc} out=${clean})"
  fi
  # Document whether -i + foreign stdin corrupts/fails the check.
  if [[ "$stolen_rc" -ne 0 || "$stolen" != "1" ]]; then
    ok "reproduced: docker exec -i + foreign stdin breaks/does not return 1 (rc=${stolen_rc})"
  else
    # Environment-specific; still flag as informative.
    echo "INFO  -i + stdin did not break SELECT here (rc=0); race/SSH may still apply"
    ok "documented -i risk (local stdin theft not triggered)"
  fi
fi

# ---------------------------------------------------------------------------
# 1) Database initialization idempotency
# ---------------------------------------------------------------------------
echo
echo "--- 1) ensure_postgres_database ---"
THROWAWAY_DBS=""
if [[ -n "$PG_CID" ]]; then
  DB1="hyrepath_cd_t1_$$"
  DB2="hyrepath_cd_t2_$$"
  THROWAWAY_DBS="$DB1 $DB2"

  assert_rc "create missing database" 0 ensure_postgres_database "$PG_CID" "$PGUSER" "$DB1"
  # Preserve: create a marker table then re-ensure.
  docker exec "$PG_CID" psql -U "$PGUSER" -d "$DB1" -v ON_ERROR_STOP=1 \
    -c "CREATE TABLE cd_probe(id int PRIMARY KEY); INSERT INTO cd_probe VALUES (42);" >/dev/null
  assert_rc "re-ensure existing database" 0 ensure_postgres_database "$PG_CID" "$PGUSER" "$DB1"
  marker="$(docker exec "$PG_CID" psql -U "$PGUSER" -d "$DB1" -Atc "SELECT id FROM cd_probe")"
  assert_eq "existing DB contents preserved" "$marker" "42"

  # Repeat deployment simulation (already exists path via SELECT short-circuit).
  assert_rc "third ensure is no-op success" 0 ensure_postgres_database "$PG_CID" "$PGUSER" "$DB1"

  # Concurrent initialization.
  set +e
  ensure_postgres_database "$PG_CID" "$PGUSER" "$DB2" &
  p1=$!
  ensure_postgres_database "$PG_CID" "$PGUSER" "$DB2" &
  p2=$!
  wait "$p1"
  r1=$?
  wait "$p2"
  r2=$?
  set -e
  if [[ "$r1" -eq 0 && "$r2" -eq 0 ]]; then
    ok "concurrent ensure both exit 0"
  else
    bad "concurrent ensure (rc ${r1}/${r2})"
  fi
  exists="$(docker exec "$PG_CID" psql -U "$PGUSER" -d postgres -Atc \
    "SELECT 1 FROM pg_database WHERE datname='${DB2}'")"
  assert_eq "concurrent ensure left DB present" "$exists" "1"

  # Genuine errors must not be suppressed.
  assert_rc "reject invalid db name" 1 \
    ensure_postgres_database "$PG_CID" "$PGUSER" "bad-name!"
  set +e
  ensure_postgres_database "$PG_CID" "role_does_not_exist_zz" "hyrepath_cd_bad_$$" >/dev/null 2>&1
  gen_rc=$?
  set -e
  if [[ "$gen_rc" -ne 0 ]]; then
    ok "genuine connect/role error is not suppressed (rc=${gen_rc})"
  else
    bad "genuine connect/role error was suppressed"
  fi
  # "already exists" without the DB present must still fail (do not blanket-ignore).
  set +e
  errfile="$(mktemp)"
  docker exec "$PG_CID" psql -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE langfuse OWNER ${PGUSER};" >"$errfile" 2>&1
  raw_dup_rc=$?
  set -e
  if [[ "$raw_dup_rc" -ne 0 ]] && grep -Eqi 'already exists' "$errfile"; then
    ok "raw duplicate create still errors at postgres (ensure must special-case)"
  else
    bad "expected raw duplicate create to error"
  fi
  rm -f "$errfile"

  # Production sidecar DBs: ensure is safe no-op.
  assert_rc "ensure langfuse (existing)" 0 ensure_postgres_database "$PG_CID" "$PGUSER" "langfuse"
  assert_rc "ensure glitchtip (existing)" 0 ensure_postgres_database "$PG_CID" "$PGUSER" "glitchtip"
fi

# ---------------------------------------------------------------------------
# 2) Frontend / HTTP readiness polling
# ---------------------------------------------------------------------------
echo
echo "--- 2) wait_for_http ---"
# Immediate readiness
python3 - <<'PY' &
import http.server, socketserver
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", 18081), H) as s:
    s.handle_request()
PY
HTTP_PIDS="$!"
sleep 0.2
assert_rc "immediate readiness" 0 wait_for_http "http://127.0.0.1:18081/" 5 0.2
wait $HTTP_PIDS 2>/dev/null || true
HTTP_PIDS=""

# Delayed readiness
python3 - <<'PY' &
import http.server, socketserver, time
time.sleep(2)
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", 18082), H) as s:
    s.handle_request()
PY
HTTP_PIDS="$!"
assert_rc "delayed readiness within timeout" 0 wait_for_http "http://127.0.0.1:18082/" 8 0.3
wait $HTTP_PIDS 2>/dev/null || true
HTTP_PIDS=""

# Permanent failure
assert_rc "permanent failure times out" 1 wait_for_http "http://127.0.0.1:18083/" 2 0.4

# Restart scenario: down then up mid-poll
python3 - <<'PY' &
import http.server, socketserver, time
time.sleep(2)
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", 18084), H) as s:
    s.handle_request()
PY
HTTP_PIDS="$!"
assert_rc "restart/delayed bind mid-poll" 0 wait_for_http "http://127.0.0.1:18084/" 8 0.3
wait $HTTP_PIDS 2>/dev/null || true
HTTP_PIDS=""

# Live frontend (if up): wait should succeed quickly
if curl -fsS --max-time 2 -o /dev/null "http://127.0.0.1:3000/" 2>/dev/null; then
  assert_rc "live frontend immediate" 0 wait_for_http "http://127.0.0.1:3000/" 5 1
else
  echo "SKIP  live frontend not listening"
fi

# ---------------------------------------------------------------------------
# 3) Deployment state consistency
# ---------------------------------------------------------------------------
echo
echo "--- 3) deploy state machine ---"
STATE="${TMP_ROOT}/deploy_state"
mkdir -p "$STATE"

# Failed health must not advance current_sha (simulate HISTORY only).
echo "deadbeef" >"${STATE}/candidate_sha"
assert_eq "no current before success" "$(test -f "${STATE}/current_sha" && echo yes || echo no)" "no"
{
  echo "RESULT=HEALTH_FAIL"
} >>"${STATE}/history.log"
assert_eq "health fail leaves current absent" "$(test -f "${STATE}/current_sha" && echo yes || echo no)" "no"

# Success path via record_cd_success
assert_rc "record first success" 0 record_cd_success "$STATE" "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
assert_eq "current after success" "$(cat "${STATE}/current_sha")" "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
assert_eq "no previous on first success" "$(test -f "${STATE}/previous_sha" && echo yes || echo no)" "no"

assert_rc "record second success" 0 record_cd_success "$STATE" "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
assert_eq "current advanced" "$(cat "${STATE}/current_sha")" "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
assert_eq "previous retained" "$(cat "${STATE}/previous_sha")" "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

# Regression guard: older ancestor must not overwrite newer current.
# Use real repo SHAs when possible.
newer="$(git -C "$REPO_ROOT" rev-parse HEAD)"
older="$(git -C "$REPO_ROOT" rev-parse HEAD~1 2>/dev/null || true)"
if [[ -n "$older" && "$older" != "$newer" ]]; then
  echo "$newer" >"${STATE}/current_sha"
  set +e
  (cd "$REPO_ROOT" && record_cd_success "$STATE" "$older") >/dev/null 2>&1
  reg_rc=$?
  set -e
  assert_eq "refuse regressing current_sha" "$reg_rc" "1"
  assert_eq "current unchanged after reject" "$(cat "${STATE}/current_sha")" "$newer"
else
  echo "SKIP  regress guard (need HEAD~1)"
fi

# Concurrent lock
LOCKDIR="${TMP_ROOT}/locktest"
mkdir -p "$LOCKDIR"
(
  acquire_cd_lock "$LOCKDIR"
  sleep 3
) &
holder=$!
sleep 0.3
set +e
acquire_cd_lock "$LOCKDIR" >/dev/null 2>&1
lock_rc=$?
set -e
assert_eq "flock rejects concurrent CD" "$lock_rc" "1"
wait "$holder" || true
assert_rc "flock available after release" 0 acquire_cd_lock "$LOCKDIR"

# Interrupted deploy: candidate set, current untouched
REAL_STATE_SNAP="${TMP_ROOT}/real_snap"
mkdir -p "$REAL_STATE_SNAP"
cp -a "${REPO_ROOT}/.deploy/." "$REAL_STATE_SNAP/" 2>/dev/null || true
assert_eq "host has no forged current_sha from tests" \
  "$(test -f "${REPO_ROOT}/.deploy/current_sha" && echo yes || echo no)" "no"
if grep -q 'RESULT=HEALTH_FAIL' "${REPO_ROOT}/.deploy/history.log" 2>/dev/null; then
  ok "host history retains HEALTH_FAIL (not manually marked success)"
else
  bad "expected HEALTH_FAIL in host history"
fi

# ---------------------------------------------------------------------------
# 4) Static script checks
# ---------------------------------------------------------------------------
echo
echo "--- 4) static ---"
bash -n "$SCRIPT_DIR/_common.sh" && ok "bash -n _common.sh" || bad "bash -n _common.sh"
bash -n "$SCRIPT_DIR/cd-on-host.sh" && ok "bash -n cd-on-host.sh" || bad "bash -n cd-on-host.sh"
bash -n "$SCRIPT_DIR/08-redeploy-frontend.sh" && ok "bash -n 08-redeploy-frontend.sh" || bad "bash -n 08-redeploy-frontend.sh"
bash -n "$SCRIPT_DIR/99-health.sh" && ok "bash -n 99-health.sh" || bad "bash -n 99-health.sh"

if grep -n 'docker exec -i' "$SCRIPT_DIR/cd-on-host.sh"; then
  bad "cd-on-host still uses docker exec -i"
else
  ok "cd-on-host has no docker exec -i"
fi

if grep -n 'ensure_postgres_database' "$SCRIPT_DIR/cd-on-host.sh" >/dev/null; then
  ok "cd-on-host calls ensure_postgres_database"
else
  bad "cd-on-host missing ensure_postgres_database"
fi

if grep -n 'wait_for_http' "$SCRIPT_DIR/08-redeploy-frontend.sh" >/dev/null \
  && grep -n 'wait_for_http' "$SCRIPT_DIR/99-health.sh" >/dev/null; then
  ok "frontend wait uses wait_for_http in 08 + 99"
else
  bad "wait_for_http not wired"
fi

if grep -n 'record_cd_success' "$SCRIPT_DIR/cd-on-host.sh" >/dev/null \
  && grep -n 'acquire_cd_lock' "$SCRIPT_DIR/cd-on-host.sh" >/dev/null; then
  ok "cd-on-host uses lock + record_cd_success"
else
  bad "cd-on-host missing lock/success helpers"
fi

# Health script still passes on current host (bounded)
echo
echo "--- 5) live 99-health (integration) ---"
FRONTEND_HEALTH_TIMEOUT_S=15
if bash "$SCRIPT_DIR/99-health.sh"; then
  ok "99-health.sh passes on host"
else
  bad "99-health.sh failed on host"
fi

echo
echo "=== Summary: PASS=${PASS} FAIL=${FAIL} ==="
if [[ "$FAIL" -ne 0 ]]; then
  exit 1
fi
exit 0
