#!/usr/bin/env bash
# 13-nuclear-reset.sh — guarded docker compose down -v.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

echo "WARNING: This DESTROYS all compose volumes (DB data included)."
echo "Type exactly: DESTROY-HYREPATH-VOLUMES"
read -r confirm
if [[ "$confirm" != "DESTROY-HYREPATH-VOLUMES" ]]; then
  echo "Aborted."
  exit 1
fi

echo "==> Backup first"
bash "$SCRIPT_DIR/10-backup-db.sh" || echo "Backup failed/skipped — continuing after confirm"

compose down -v
echo "Nuclear reset complete. Re-run 01-full-up.sh to rebuild."
