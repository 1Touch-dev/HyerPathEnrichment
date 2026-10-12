#!/usr/bin/env bash
# 12-restore-db.sh — restore dump then forward-migrate only (never alembic downgrade).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <backup.sql.gz>" >&2
  exit 1
fi
BACKUP="$1"
cid="$(postgres_container)"
name="$(docker inspect -f '{{.Name}}' "$cid" | sed 's#^/##')"
export POSTGRES_CONTAINER="$name"
export POSTGRES_USER="$(env_get POSTGRES_USER)"
export POSTGRES_DB="$(env_get POSTGRES_DB)"
export COMPOSE_DIR="$COMPOSE_DIR"
# Non-interactive restore path
gunzip -c "$BACKUP" | docker exec -i "$cid" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
echo "Restore loaded. Running forward migrate…"
compose up -d migrate
compose up -d --force-recreate api
echo "Restore + migrate complete."
