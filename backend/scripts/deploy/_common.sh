#!/usr/bin/env bash
# Shared helpers for Day-1 EC2 deploy scripts (plan.md).
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$DEPLOY_DIR/../.." && pwd)"
REPO_ROOT="$(cd "$BACKEND_DIR/.." && pwd)"
COMPOSE_DIR="$BACKEND_DIR/docker"
ENV_FILE="${HYREPATH_ENV_FILE:-$BACKEND_DIR/.env.production}"
FRONTEND_DIR="$REPO_ROOT/frontend"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

env_get() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//" || true
}

# staging.yml is last so its APP_ENV=staging wins over tier-workers `extends`
# (which re-pulls APP_ENV=${APP_ENV} from --env-file, often "production").
DAY1_FILES=(
  -f docker-compose.yml
  -f docker-compose.foundation.yml
  -f docker-compose.week2-ai.yml
  -f docker-compose.tier-workers.yml
  -f docker-compose.staging.yml
)

DAY1_PROFILES=(
  --profile paid
  --profile llm
  --profile observability
  --profile scrapoxy
)

DAY1_SERVICES=(
  migrate api redis postgres
  worker worker-email worker-cleanup worker-tier234
  social-analyzer google-maps-scraper email-verifier
  worker-document worker-embedding worker-job-matching worker-interview-ai
  reacher litellm scrapoxy
  langfuse changedetection
  glitchtip-migrate glitchtip-web glitchtip-worker
)

# App services whose images CD pins to :<sha>. Sidecars stay public/host images.
CD_APP_SERVICES=(
  migrate api
  worker worker-email worker-cleanup worker-tier234 worker-interview-ai
  worker-document worker-embedding worker-job-matching
)

compose() {
  (
    cd "$COMPOSE_DIR"
    docker compose "${DAY1_FILES[@]}" --env-file "$ENV_FILE" "${DAY1_PROFILES[@]}" "$@"
  )
}

postgres_container() {
  compose ps -q postgres | head -n1
}

api_host_port() {
  local p
  p="$(env_get API_HOST_PORT)"
  echo "${p:-8000}"
}

glitchtip_host_port() {
  local p
  p="$(env_get GLITCHTIP_HOST_PORT)"
  echo "${p:-8001}"
}

langfuse_host_port() {
  local p
  p="$(env_get LANGFUSE_HOST_PORT)"
  echo "${p:-3002}"
}

# Bounded HTTP readiness poll. Returns 0 when curl succeeds, 1 on timeout.
# Usage: wait_for_http URL TIMEOUT_SECONDS [SLEEP_SECONDS]
# Note: never toggles `set -e` (leaks into callers and aborts on non-zero return).
wait_for_http() {
  local url="$1"
  local timeout_s="${2:?timeout seconds required}"
  local sleep_s="${3:-1}"
  local start now elapsed
  start="$(date +%s)"
  while true; do
    if curl -fsS --max-time 2 -o /dev/null "$url" 2>/dev/null; then
      return 0
    fi
    now="$(date +%s)"
    elapsed=$((now - start))
    if [[ "$elapsed" -ge "$timeout_s" ]]; then
      echo "ERROR: timed out after ${timeout_s}s waiting for ${url}" >&2
      return 1
    fi
    sleep "$sleep_s"
  done
}

# Idempotent CREATE DATABASE for Day-1 sidecars (langfuse/glitchtip).
# - No `docker exec -i` (SSH CD feeds the remote script on stdin; `-i` can
#   steal that stdin and make the existence check flaky).
# - Safe if the DB already exists or a concurrent create wins (42P04).
# - Does not DROP/ALTER existing DBs; genuine create/connect errors still fail.
# Usage: ensure_postgres_database CONTAINER_ID PGUSER DBNAME
ensure_postgres_database() {
  local cid="$1"
  local pguser="$2"
  local db="$3"
  local errfile check_out check_rc create_rc

  if [[ ! "$db" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    echo "ERROR: invalid database name: ${db}" >&2
    return 1
  fi
  if [[ ! "$pguser" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    echo "ERROR: invalid postgres role: ${pguser}" >&2
    return 1
  fi

  # `||` keeps set -e from aborting; connect failures must not fall through to CREATE.
  check_rc=0
  check_out="$(docker exec "$cid" psql -U "$pguser" -d postgres -Atc \
    "SELECT 1 FROM pg_database WHERE datname='${db}'" 2>&1)" || check_rc=$?
  if [[ "$check_rc" -ne 0 ]]; then
    echo "$check_out" >&2
    return "$check_rc"
  fi
  if [[ "$(echo "$check_out" | tr -d '[:space:]')" == "1" ]]; then
    return 0
  fi

  errfile="$(mktemp)"
  create_rc=0
  docker exec "$cid" psql -U "$pguser" -d postgres -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE ${db} OWNER ${pguser};" >"$errfile" 2>&1 || create_rc=$?
  if [[ "$create_rc" -eq 0 ]]; then
    rm -f "$errfile"
    return 0
  fi

  # Concurrent/repeated create: duplicate_database — accept only if DB exists now.
  if grep -Eqi 'already exists|SQLSTATE\[42P04\]|42P04' "$errfile"; then
    check_rc=0
    check_out="$(docker exec "$cid" psql -U "$pguser" -d postgres -Atc \
      "SELECT 1 FROM pg_database WHERE datname='${db}'" 2>&1)" || check_rc=$?
    if [[ "$check_rc" -eq 0 && "$(echo "$check_out" | tr -d '[:space:]')" == "1" ]]; then
      rm -f "$errfile"
      return 0
    fi
  fi

  cat "$errfile" >&2
  rm -f "$errfile"
  return "$create_rc"
}

# Exclusive CD lock under .deploy/ (fd 9). Non-blocking; fails if held.
# Usage: acquire_cd_lock DEPLOY_STATE_DIR
acquire_cd_lock() {
  local state_dir="$1"
  mkdir -p "$state_dir"
  exec 9>"${state_dir}/lock"
  if ! flock -n 9; then
    echo "ERROR: another CD run holds ${state_dir}/lock; refusing concurrent deploy" >&2
    return 1
  fi
}

# Advance success marker only after health. Refuses to regress main history.
# Usage: record_cd_success DEPLOY_STATE_DIR DEPLOY_SHA
record_cd_success() {
  local state_dir="$1"
  local sha="$2"
  local cur

  mkdir -p "$state_dir"
  if [[ -f "${state_dir}/current_sha" ]]; then
    cur="$(tr -d '[:space:]' <"${state_dir}/current_sha")"
    if [[ -n "$cur" && "$cur" != "$sha" ]]; then
      if git -C "$REPO_ROOT" merge-base --is-ancestor "$sha" "$cur" 2>/dev/null; then
        echo "ERROR: current_sha ${cur} is ahead of DEPLOY_SHA ${sha}; not regressing success marker" >&2
        return 1
      fi
    fi
    cp "${state_dir}/current_sha" "${state_dir}/previous_sha"
  fi
  echo "$sha" >"${state_dir}/current_sha"
}
