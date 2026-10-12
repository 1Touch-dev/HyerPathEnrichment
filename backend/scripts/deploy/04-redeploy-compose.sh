#!/usr/bin/env bash
# 04-redeploy-compose.sh — re-apply full Day-1 compose topology.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

compose up -d --build "${DAY1_SERVICES[@]}"
echo "Day-1 compose re-applied."
