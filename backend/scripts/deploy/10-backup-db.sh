#!/usr/bin/env bash
# 10-backup-db.sh — Postgres backup wrapper.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

export BACKUP_DIR="${BACKUP_DIR:-/home/ubuntu/backups/postgres}"
export RETENTION_DAYS="${RETENTION_DAYS:-30}"
cid="$(postgres_container)"
if [[ -z "$cid" ]]; then
  echo "ERROR: postgres not running" >&2
  exit 1
fi
# backup_postgres.sh expects container name; pass via env
name="$(docker inspect -f '{{.Name}}' "$cid" | sed 's#^/##')"
export POSTGRES_CONTAINER="$name"
export POSTGRES_USER
POSTGRES_USER="$(env_get POSTGRES_USER)"
export POSTGRES_DB
POSTGRES_DB="$(env_get POSTGRES_DB)"
bash "$BACKEND_DIR/scripts/backup_postgres.sh"
