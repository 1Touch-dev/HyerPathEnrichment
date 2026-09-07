#!/usr/bin/env bash
# Start the backend the way it runs in production: base compose + the
# production overlay (docker-compose.prod.yml), plus the foundation overlay
# (docker-compose.foundation.yml) for the dedicated job-matching worker,
# audio-cleanup scheduler seeding, and the maintenance worker,
# optionally + the Tier 1
# overlay (docker-compose.tier1.yml) when ENABLE_TIER1=true, optionally
# + the tier-workers overlay (docker-compose.tier-workers.yml) for
# dedicated tier-specific worker pools, and optionally + the Linux
# Multilogin overlay (docker-compose.multilogin.yml) when --with-linux-mlx
# is passed.
#
# This is the reusable "run the backend for production" entrypoint — use it
# for any production-shaped start, not just one-off test runs.
#
# Usage:
#   bash backend/scripts/start_production.sh
#   bash backend/scripts/start_production.sh --with-tier1
#   bash backend/scripts/start_production.sh --with-linux-mlx
#   bash backend/scripts/start_production.sh --with-tier-workers
#   bash backend/scripts/start_production.sh --with-tier1 --with-tier-workers --with-linux-mlx
#   bash backend/scripts/start_production.sh --down          # tear the stack down
#   bash backend/scripts/start_production.sh --dry-run       # print resolved plan only
#
# Env:
#   API_ENV_FILE     path to prod env file for the api service   (default: backend/.env.production)
#   WORKER_ENV_FILE  path to prod env file for the worker service (default: backend/.env.production)
#   ENABLE_TIER1     "true" to also load docker-compose.tier1.yml (default: read from env file)
#   ENABLE_LINUX_MLX "true" to also load docker-compose.multilogin.yml (default: read from env file)
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
#                    build-time credentials for Dockerfile.multilogin; these must
#                    live in API_ENV_FILE / the compose --env-file because Docker
#                    Compose resolves build args from that source, not WORKER_ENV_FILE
#   MULTILOGIN_HOST_IP  Windows host IP for WSL2 + Docker Engine (auto-detected under WSL,
#                       ignored when --with-linux-mlx is set)
#
# Required in the supported env file: API_TOKEN, DATABASE_URL, REDIS_URL,
# POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, WORKER_QUEUE_MODE, and
# OUTREACH_PHYSICAL_ADDRESS (unless OUTREACH_ENABLED=false). validate_env.sh
# enforces the broader startup contract before launch.
#
# Tier 1 paths:
#   --with-tier1 alone       WSL2/Windows: Multilogin runs on Windows host; worker
#                            reaches it via host IP mapping.  Selenium debug port is
#                            127.0.0.1-bound on Windows and unreachable from WSL2 —
#                            suitable for launcher API testing only.
#   --with-linux-mlx         Bare Linux: starts the containerised Multilogin service
#                            and implies the supported tier-worker topology. Tier 1
#                            keeps the required localhost rewrites and explicit queue
#                            assignment while the bridge-network worker keeps the
#                            already-built non-tier queues (including
#                            `audio_cleanup`), the dedicated job-matching
#                            worker seeds `job_matching` + `audio_cleanup`
#                            schedules, `worker-email` drains digest mail from
#                            the `email` queue, and `worker-cleanup` handles
#                            orphan-job maintenance. Both containers share the
#                            Linux 127.0.0.1 loopback. See ADR 0008.
#   --with-tier-workers      Use dedicated tier-specific worker pools (tier1, tier234)
#                            with hybrid networking (host for tier1, bridge for tier234).
#                            Enables horizontal scaling of tier 2-4 workers.
#
# docker-compose.prod.yml pins ports to 127.0.0.1 only and expects TLS to
# terminate at a reverse proxy in front of this host (see docs/deployment.md).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${API_ENV_FILE:-$BACKEND_DIR/.env.production}"
BASE="http://localhost:8000"

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1" >&2; exit 1; }
warn() { echo "WARN  $1"; }

detect_host_platform() {
  if [ -n "${START_PRODUCTION_HOST_PLATFORM:-}" ]; then
    echo "$START_PRODUCTION_HOST_PLATFORM"
    return
  fi

  if [ -f /proc/version ] && grep -qi microsoft /proc/version 2>/dev/null; then
    echo "wsl"
    return
  fi

  case "$(uname -s 2>/dev/null | tr '[:upper:]' '[:lower:]')" in
    linux*) echo "linux" ;;
    *) echo "other" ;;
  esac
}

WITH_TIER1=0
WITH_TIER_WORKERS=0
WITH_LINUX_MLX=0
DOWN=0
SKIP_VALIDATION=0
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --with-tier1)        WITH_TIER1=1 ;;
    --with-tier-workers) WITH_TIER_WORKERS=1 ;;
    --with-linux-mlx)    WITH_LINUX_MLX=1 ;;
    --down)              DOWN=1 ;;
    --skip-validation)   SKIP_VALIDATION=1 ;;
    --dry-run)           DRY_RUN=1 ;;
    *) fail "unknown argument: $arg" ;;
  esac
done

if [ ! -f "$ENV_FILE" ]; then
  fail "$ENV_FILE not found - create it (see backend/docker/docker-compose.prod.yml header) before a production start"
fi

require_var() {
  local name="$1"
  if ! grep -qE "^${name}=.+" "$ENV_FILE"; then
    fail "$name is not set in $ENV_FILE"
  fi
}
require_var API_TOKEN
require_var POSTGRES_USER
require_var POSTGRES_PASSWORD

if [ "$WITH_TIER1" -eq 0 ] && grep -qE '^ENABLE_TIER1=true' "$ENV_FILE"; then
  WITH_TIER1=1
fi

if [ "$WITH_LINUX_MLX" -eq 0 ] && grep -qE '^ENABLE_LINUX_MLX=true' "$ENV_FILE"; then
  WITH_LINUX_MLX=1
fi

# --with-linux-mlx implies --with-tier1
if [ "$WITH_LINUX_MLX" -eq 1 ] && [ "$WITH_TIER1" -eq 0 ]; then
  WITH_TIER1=1
  warn "--with-linux-mlx implies --with-tier1 (enabling)"
fi

# The production env contract routes jobs per tier. A generic worker without an
# explicit WORKER_TARGET_QUEUE will fail at boot, so prefer the dedicated
# tier-workers topology whenever the env or Linux MLX path requires it.
if [ "$WITH_TIER_WORKERS" -eq 0 ] && grep -qE '^WORKER_QUEUE_MODE=per_tier' "$ENV_FILE"; then
  WITH_TIER_WORKERS=1
  warn "WORKER_QUEUE_MODE=per_tier requires tier-specific workers (enabling --with-tier-workers)"
fi

if [ "$WITH_LINUX_MLX" -eq 1 ] && [ "$WITH_TIER_WORKERS" -eq 0 ]; then
  WITH_TIER_WORKERS=1
  warn "--with-linux-mlx requires tier-specific workers on Linux (enabling --with-tier-workers)"
fi

HOST_PLATFORM="$(detect_host_platform)"
if [ "$HOST_PLATFORM" = "linux" ] && [ "$WITH_TIER1" -eq 1 ] && [ "$WITH_LINUX_MLX" -eq 0 ]; then
  fail "real Linux Tier 1 requires --with-linux-mlx / ENABLE_LINUX_MLX=true; docker-compose.tier1.yml is diagnostic-only for WSL2/Windows"
fi

# --with-tier-workers implies --with-tier1 if tier1 is enabled in env
if [ "$WITH_TIER_WORKERS" -eq 1 ] && [ "$WITH_TIER1" -eq 1 ]; then
  warn "--with-tier-workers: using dedicated tier-specific worker pools"
fi

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.foundation.yml)

# Choose between single worker or tier-workers
if [ "$WITH_TIER_WORKERS" -eq 1 ]; then
  # Use dedicated tier-specific workers (hybrid networking)
  COMPOSE_FILES+=(-f docker-compose.tier-workers.yml)
  export WORKER_ENV_FILE="${WORKER_ENV_FILE:-$ENV_FILE}"
elif [ "$WITH_TIER1" -eq 1 ]; then
  # Use single worker with tier1 enabled (legacy path)
  COMPOSE_FILES+=(-f docker-compose.tier1.yml)
  export WORKER_ENV_FILE="${WORKER_ENV_FILE:-$ENV_FILE}"
fi

if [ "$WITH_LINUX_MLX" -eq 1 ]; then
  COMPOSE_FILES+=(-f docker-compose.multilogin.yml)
fi
export API_ENV_FILE="$ENV_FILE"

# ============================================================================
# Run environment validation against the effective runtime contract
# ============================================================================
if [ "$DOWN" -eq 0 ] && [ "$SKIP_VALIDATION" -eq 0 ]; then
  echo "== validating environment configuration =="
  if ! VALIDATE_WORKER_ENV_FILE="$WORKER_ENV_FILE" \
       VALIDATE_EFFECTIVE_TIER1="$([ "$WITH_TIER1" -eq 1 ] && echo true || echo false)" \
       VALIDATE_EFFECTIVE_LINUX_MLX="$([ "$WITH_LINUX_MLX" -eq 1 ] && echo true || echo false)" \
       bash "$SCRIPT_DIR/validate_env.sh" "$ENV_FILE"; then
    fail "environment validation failed - fix errors above before starting"
  fi
  echo ""
fi

cd "$COMPOSE_DIR"

if [ "$DOWN" -eq 1 ]; then
  echo "== stopping production stack =="
  docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" down --remove-orphans
  pass "production stack stopped"
  exit 0
fi

# WSL2 + Docker Engine: host-gateway resolves to the WSL VM, not the Windows
# host running Multilogin. Auto-detect the Windows host via the WSL default
# route unless already set (see docker-compose.tier1.yml).
# Skip this block entirely when --with-linux-mlx is set — on bare Linux there
# is no Windows host; Multilogin runs in a container sharing 127.0.0.1.
if [ "$WITH_TIER1" -eq 1 ] && [ "$WITH_LINUX_MLX" -eq 0 ] \
  && [ -z "${MULTILOGIN_HOST_IP:-}" ] \
  && [ -f /proc/version ] && grep -qi microsoft /proc/version 2>/dev/null; then
  detected_host_ip="$(ip route show default 2>/dev/null | awk '{print $3}' | head -n1)"
  if [ -n "$detected_host_ip" ]; then
    export MULTILOGIN_HOST_IP="$detected_host_ip"
    warn "auto-detected MULTILOGIN_HOST_IP=$MULTILOGIN_HOST_IP (WSL2 default route to Windows host)"
  fi
fi

tier1_label="off"
if [ "$WITH_TIER1" -eq 1 ]; then
  if [ "$WITH_LINUX_MLX" -eq 1 ]; then
    tier1_label="on (linux-mlx)"
  else
    tier1_label="on (wsl2/windows)"
  fi
fi

workers_label="single"
if [ "$WITH_TIER_WORKERS" -eq 1 ]; then
  workers_label="supported (aux + email + cleanup + job-matching + tier234)"
  if [ "$WITH_TIER1" -eq 1 ]; then
    workers_label="supported (aux + email + cleanup + job-matching + tier1 + tier234)"
  fi
fi

SERVICES=(migrate api redis postgres social-analyzer google-maps-scraper email-verifier worker-email worker-cleanup worker-job-matching)
if [ "$WITH_TIER_WORKERS" -eq 1 ]; then
  SERVICES+=(worker worker-tier234)
  [ "$WITH_TIER1" -eq 1 ] && SERVICES+=(worker-tier1)
  [ "$WITH_LINUX_MLX" -eq 1 ] && SERVICES+=(multilogin)
else
  SERVICES+=(worker)
  [ "$WITH_LINUX_MLX" -eq 1 ] && SERVICES+=(multilogin)
fi

echo "== starting production stack =="
echo "   env: $ENV_FILE"
echo "   tier1: $tier1_label"
echo "   workers: $workers_label"
echo ""

if [ "$DRY_RUN" -eq 1 ]; then
  echo "== dry run =="
  echo "   compose files: ${COMPOSE_FILES[*]}"
  echo "   services: ${SERVICES[*]}"
  echo "   remove orphans: yes"
  pass "dry run complete"
  exit 0
fi

# Start services based on configuration
if [ "$WITH_TIER_WORKERS" -eq 1 ]; then
  # Start with supported production workers:
  # - worker: non-tier queues on bridge network
  # - worker-tier1: Tier 1 enrichment on host network
  # - worker-tier234: Tier 2-4 enrichment on bridge network
  docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" up --remove-orphans --build -d \
    "${SERVICES[@]}"
else
  # Start with single worker
  docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" up --remove-orphans --build -d \
    "${SERVICES[@]}"
fi

echo "== wait for API health =="
for i in $(seq 1 90); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health" || true)"
  [ "$code" = "200" ] && break
  sleep 3
done
[ "$code" = "200" ] || fail "API health never returned 200 (last=$code)"
pass "api health 200"

if [ "$WITH_LINUX_MLX" -eq 1 ]; then
  echo "== wait for Multilogin healthcheck =="
  for i in $(seq 1 20); do
    mlx_status="$(docker inspect --format='{{.State.Health.Status}}' hyrepath-multilogin 2>/dev/null || echo "starting")"
    [ "$mlx_status" = "healthy" ] && break
    [ "$i" -eq 20 ] && warn "multilogin healthcheck not yet healthy after 60s — check 'docker logs hyrepath-multilogin'"
    sleep 3
  done
  [ "${mlx_status:-}" = "healthy" ] && pass "multilogin healthy" || warn "multilogin not yet healthy"
fi

wait_for_container_health() {
  local container_name="$1"
  local label="$2"
  local attempts="${3:-20}"
  local status="starting"

  for _ in $(seq 1 "$attempts"); do
    status="$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "not found")"
    if [ "$status" = "healthy" ]; then
      pass "$label healthy"
      return 0
    fi
    sleep 3
  done

  fail "$label status: $status"
}

echo "== checking queue consumers =="
wait_for_container_health docker-worker-email-1 "worker-email"
wait_for_container_health docker-worker-cleanup-1 "worker-cleanup"
wait_for_container_health docker-worker-job-matching-1 "worker-job-matching"

if [ "$WITH_TIER_WORKERS" -eq 1 ]; then
  wait_for_container_health docker-worker-1 "worker"
  wait_for_container_health docker-worker-tier234-1 "worker-tier234"
  if [ "$WITH_TIER1" -eq 1 ]; then
    wait_for_container_health docker-worker-tier1-1 "worker-tier1"
  fi
fi

echo ""
docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" ps
echo ""
echo "Production stack is up. Stop it with:"
down_flags="--down"
[ "$WITH_TIER1" -eq 1 ] && down_flags="$down_flags --with-tier1"
[ "$WITH_TIER_WORKERS" -eq 1 ] && down_flags="$down_flags --with-tier-workers"
[ "$WITH_LINUX_MLX" -eq 1 ] && down_flags="$down_flags --with-linux-mlx"
echo "  bash $SCRIPT_DIR/start_production.sh $down_flags"
echo ""

if [ "$WITH_TIER_WORKERS" -eq 1 ]; then
  echo "Scale tier 2-4 workers with:"
  echo "  cd backend/docker"
  echo "  docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.foundation.yml -f docker-compose.tier-workers.yml up -d api worker worker-email worker-cleanup worker-job-matching --scale worker-tier234=N"
  echo ""
fi
