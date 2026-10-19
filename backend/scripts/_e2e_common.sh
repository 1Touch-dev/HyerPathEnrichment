#!/usr/bin/env bash
# Shared helpers for compose-backed E2E scripts.
#
# Compose defaults OUTREACH_ENABLED=true. An empty physical address makes the
# API lifespan fail-closed (CAN-SPAM) so /health never binds — the same failure
# docker-smoke already documents in .github/workflows/ci.yml.

e2e_default_outreach_address() {
  printf '%s' "123 Main St, Suite 100, San Francisco, CA 94105"
}

e2e_export_staff_defaults() {
  export E2E_USER_EMAIL="${E2E_USER_EMAIL:-e2e-fullpath@example.com}"
  export E2E_USER_PASSWORD="${E2E_USER_PASSWORD:-IntegrationTest123}"
}

e2e_export_compose_defaults() {
  export OUTREACH_PHYSICAL_ADDRESS="${OUTREACH_PHYSICAL_ADDRESS:-$(e2e_default_outreach_address)}"
  e2e_export_staff_defaults
}

e2e_seed_verified_staff() {
  e2e_export_staff_defaults
  docker compose "$@" exec -T \
    -e E2E_USER_EMAIL="$E2E_USER_EMAIL" \
    -e E2E_USER_PASSWORD="$E2E_USER_PASSWORD" \
    -e ALLOW_E2E_SUPERUSER_BOOTSTRAP=1 \
    -e PYTHONPATH=/app/backend \
    api sh -c \
    'python - --email "$E2E_USER_EMAIL" --password "$E2E_USER_PASSWORD" --is-superuser' \
    < "${E2E_CREATE_TEST_USER:-$SCRIPT_DIR/create_test_user.py}"
}

e2e_login_cookie_header() {
  local base="${1:?base url required}"
  local cookie_file body_file login_code token
  e2e_export_staff_defaults
  cookie_file="$(mktemp)"
  body_file="$(mktemp)"
  login_code="$(
    curl -s -o "$body_file" -w '%{http_code}' -c "$cookie_file" \
      -X POST "$base/auth/login" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"${E2E_USER_EMAIL}\",\"password\":\"${E2E_USER_PASSWORD}\"}" || true
  )"
  if [ "$login_code" != "200" ]; then
    echo "login failed status=${login_code} body=$(cat "$body_file" 2>/dev/null || true)" >&2
    rm -f "$cookie_file" "$body_file"
    return 1
  fi
  token="$(awk '$0 ~ /(^|[[:space:]])access_token[[:space:]]/ { print $NF }' "$cookie_file")"
  rm -f "$cookie_file" "$body_file"
  if [ -z "$token" ]; then
    echo "login missing access_token cookie" >&2
    return 1
  fi
  printf 'Cookie: access_token=%s' "$token"
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
