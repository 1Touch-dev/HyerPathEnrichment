#!/usr/bin/env bash
# 03-redeploy-code.sh — rebuild and recreate named services.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <service> [service…]" >&2
  exit 1
fi

compose up -d --build --force-recreate --no-deps "$@"
