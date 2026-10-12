#!/usr/bin/env bash
# 01-full-up.sh — Day-1 full stack (no Multilogin). Soft-warn non-boot env keys.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

echo "==> Env report (warn-only for non-boot)"
bash "$SCRIPT_DIR/07-env-report.sh" || true

echo "==> Validating boot-required keys"
BOOT_KEYS=(APP_ENV API_TOKEN SECRET_KEY COOKIE_SECURE CHANGEDETECTION_API_KEY POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB DATABASE_URL REDIS_URL WORKER_QUEUE_MODE)
fail=0
for k in "${BOOT_KEYS[@]}"; do
  v="$(env_get "$k")"
  if [[ -z "$v" || "$v" == REPLACE_* || "$v" == change-me* || "$v" == your-* ]]; then
    echo "BOOT FAIL: $k is empty or placeholder" >&2
    fail=1
  fi
done
if [[ "$(env_get OUTREACH_ENABLED)" == "true" ]]; then
  if [[ -z "$(env_get OUTREACH_PHYSICAL_ADDRESS)" ]]; then
    echo "BOOT FAIL: OUTREACH_ENABLED=true but OUTREACH_PHYSICAL_ADDRESS empty" >&2
    fail=1
  fi
fi
if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "Boot keys OK"

echo "==> Start postgres + redis first (for obs DB create)"
compose up -d --build postgres redis

echo "==> Waiting for postgres healthy"
for i in $(seq 1 90); do
  cid="$(postgres_container)"
  if [[ -n "$cid" ]] && docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null | grep -q healthy; then
    break
  fi
  sleep 2
done
cid="$(postgres_container)"
if [[ -z "$cid" ]]; then
  echo "ERROR: postgres did not become healthy" >&2
  exit 1
fi

echo "==> Ensuring langfuse + glitchtip databases exist"
PGUSER="$(env_get POSTGRES_USER)"
PGUSER="${PGUSER:-hyrepath}"
for db in langfuse glitchtip; do
  docker exec -i "$cid" psql -U "$PGUSER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='${db}'" | grep -q 1 \
    || docker exec -i "$cid" psql -U "$PGUSER" -d postgres -c "CREATE DATABASE ${db} OWNER ${PGUSER};"
done

echo "==> Bringing up full Day-1 compose (build)"
compose up -d --build "${DAY1_SERVICES[@]}"

echo "==> Day-1 full-up complete. Next: 06-seed-god-user.sh, 08-redeploy-frontend.sh, 99-health.sh"
