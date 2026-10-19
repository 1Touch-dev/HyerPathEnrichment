#!/usr/bin/env bash
# Shared helpers for compose-backed E2E scripts.
#
# Compose defaults OUTREACH_ENABLED=true. An empty physical address makes the
# API lifespan fail-closed (CAN-SPAM) so /health never binds — the same failure
# docker-smoke already documents in .github/workflows/ci.yml.

e2e_default_outreach_address() {
  printf '%s' "123 Main St, Suite 100, San Francisco, CA 94105"
}

e2e_export_compose_defaults() {
  export OUTREACH_PHYSICAL_ADDRESS="${OUTREACH_PHYSICAL_ADDRESS:-$(e2e_default_outreach_address)}"
}

e2e_wait_for_health() {
  local base="${1:?base url required}"
  shift
  E2E_LAST_HEALTH_CODE="000"
  local i
  for i in $(seq 1 60); do
    E2E_LAST_HEALTH_CODE="$(curl -s -o /dev/null -w '%{http_code}' "$base/health" || true)"
    if [ "$E2E_LAST_HEALTH_CODE" = "200" ]; then
      return 0
    fi
    sleep 2
  done
  echo "== api logs (health last=${E2E_LAST_HEALTH_CODE}) ==" >&2
  docker compose "$@" logs --tail 120 api >&2 || true
  return 1
}
