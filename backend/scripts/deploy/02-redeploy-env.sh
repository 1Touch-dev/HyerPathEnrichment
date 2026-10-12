#!/usr/bin/env bash
# 02-redeploy-env.sh — force-recreate services that read env.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <service> [service…]" >&2
  exit 1
fi

compose up -d --force-recreate --no-deps "$@"
bash "$SCRIPT_DIR/07-env-report.sh" || true
