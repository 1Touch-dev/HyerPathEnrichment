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

DAY1_FILES=(
  -f docker-compose.yml
  -f docker-compose.staging.yml
  -f docker-compose.foundation.yml
  -f docker-compose.week2-ai.yml
  -f docker-compose.tier-workers.yml
)

DAY1_PROFILES=(
  --profile llm
  --profile observability
  --profile ollama
)

DAY1_SERVICES=(
  migrate api redis postgres
  worker worker-email worker-cleanup worker-tier234
  social-analyzer google-maps-scraper email-verifier
  worker-document worker-embedding worker-job-matching worker-interview-ai
  reacher litellm ollama
  langfuse changedetection
  glitchtip-migrate glitchtip-web glitchtip-worker
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
