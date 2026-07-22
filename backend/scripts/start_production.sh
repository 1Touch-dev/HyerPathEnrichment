#!/usr/bin/env bash
# Start the backend the way it runs in production: base compose + the
# production overlay (docker-compose.prod.yml), optionally + the Tier 1
# overlay (docker-compose.tier1.yml) when ENABLE_TIER1=true, and optionally
# + the Linux Multilogin overlay (docker-compose.multilogin.yml) when
# --with-linux-mlx is passed.
#
# This is the reusable "run the backend for production" entrypoint — use it
# for any production-shaped start, not just one-off test runs.
#
# Usage:
#   bash backend/scripts/start_production.sh
#   bash backend/scripts/start_production.sh --with-tier1
#   bash backend/scripts/start_production.sh --with-tier1 --with-linux-mlx
#   bash backend/scripts/start_production.sh --down          # tear the stack down
#
# Env:
#   API_ENV_FILE     path to prod env file for the api service   (default: backend/.env.production)
#   WORKER_ENV_FILE  path to prod env file for the worker service (default: backend/.env.production)
#   ENABLE_TIER1     "true" to also load docker-compose.tier1.yml (default: read from env file)
#   ENABLE_LINUX_MLX "true" to also load docker-compose.multilogin.yml (default: read from env file)
#   MULTILOGIN_HOST_IP  Windows host IP for WSL2 + Docker Engine (auto-detected under WSL,
#                       ignored when --with-linux-mlx is set)
#
# Required in the env file: API_TOKEN, DATABASE_URL, REDIS_URL, POSTGRES_USER, POSTGRES_PASSWORD
#
# Tier 1 paths:
#   --with-tier1 alone       WSL2/Windows: Multilogin runs on Windows host; worker
#                            reaches it via host IP mapping.  Selenium debug port is
#                            127.0.0.1-bound on Windows and unreachable from WSL2 —
#                            suitable for launcher API testing only.
#   --with-tier1             Bare Linux: add --with-linux-mlx to also start the
#     --with-linux-mlx       containerised Multilogin service (network_mode: host).
#                            Both containers share the Linux 127.0.0.1 loopback;
#                            Tier 1 works end-to-end. See ADR 0008.
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

WITH_TIER1=0
WITH_LINUX_MLX=0
DOWN=0
for arg in "$@"; do
  case "$arg" in
    --with-tier1)     WITH_TIER1=1 ;;
    --with-linux-mlx) WITH_LINUX_MLX=1 ;;
    --down)           DOWN=1 ;;
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
require_var DATABASE_URL
require_var REDIS_URL
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

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml)
if [ "$WITH_TIER1" -eq 1 ]; then
  COMPOSE_FILES+=(-f docker-compose.tier1.yml)
  export WORKER_ENV_FILE="${WORKER_ENV_FILE:-$ENV_FILE}"
fi
if [ "$WITH_LINUX_MLX" -eq 1 ]; then
  COMPOSE_FILES+=(-f docker-compose.multilogin.yml)
fi
export API_ENV_FILE="$ENV_FILE"

cd "$COMPOSE_DIR"

if [ "$DOWN" -eq 1 ]; then
  echo "== stopping production stack =="
  docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" down
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

echo "== starting production stack (env=$ENV_FILE, tier1=$tier1_label) =="
docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" up --build -d \
  migrate api worker redis postgres social-analyzer google-maps-scraper email-verifier \
  $([ "$WITH_LINUX_MLX" -eq 1 ] && echo "multilogin" || true)

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

echo ""
docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" ps
echo ""
echo "Production stack is up. Stop it with:"
down_flags="--down"
[ "$WITH_TIER1" -eq 1 ] && down_flags="$down_flags --with-tier1"
[ "$WITH_LINUX_MLX" -eq 1 ] && down_flags="$down_flags --with-linux-mlx"
echo "  bash $SCRIPT_DIR/start_production.sh $down_flags"
