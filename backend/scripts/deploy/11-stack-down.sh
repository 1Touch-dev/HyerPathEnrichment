#!/usr/bin/env bash
# 11-stack-down.sh — safe stop without wiping volumes.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

compose down
echo "Stack stopped (volumes preserved)."
