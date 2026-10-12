#!/usr/bin/env bash
# 99-health.sh — probe API + HyrePath UI + observability UIs.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

API_PORT="$(api_host_port)"
GT_PORT="$(glitchtip_host_port)"
LF_PORT="$(langfuse_host_port)"
fail=0

probe() {
  local name="$1" url="$2"
  if curl -fsS --max-time 10 -o /dev/null "$url"; then
    echo "OK  $name  $url"
  else
    echo "FAIL $name  $url" >&2
    fail=1
  fi
}

probe "api /health" "http://127.0.0.1:${API_PORT}/health"
probe "api /ready"  "http://127.0.0.1:${API_PORT}/ready"
probe "frontend"    "http://127.0.0.1:3000/"
probe "langfuse"    "http://127.0.0.1:${LF_PORT}/"
probe "glitchtip"   "http://127.0.0.1:${GT_PORT}/"
probe "changedetection" "http://127.0.0.1:5000/"

if [[ "$fail" -ne 0 ]]; then
  echo "Health check FAILED" >&2
  exit 1
fi
echo "All health probes passed."
