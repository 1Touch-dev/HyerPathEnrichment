#!/usr/bin/env bash
# 05-deploy-multilogin.sh — Multilogin + worker-tier1 (later; not Day-1).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

if [[ "$(env_get ENABLE_TIER1)" != "true" || "$(env_get ENABLE_LINUX_MLX)" != "true" ]]; then
  echo "Set ENABLE_TIER1=true and ENABLE_LINUX_MLX=true in $ENV_FILE first." >&2
  exit 1
fi

(
  cd "$COMPOSE_DIR"
  docker compose \
    -f docker-compose.yml \
    -f docker-compose.staging.yml \
    -f docker-compose.foundation.yml \
    -f docker-compose.tier-workers.yml \
    -f docker-compose.multilogin.yml \
    --env-file "$ENV_FILE" \
    up -d --build multilogin worker-tier1
)
echo "Multilogin path deployed. Run 99-health.sh and verify Tier 1."
