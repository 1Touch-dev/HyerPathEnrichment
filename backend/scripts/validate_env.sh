#!/usr/bin/env bash
# Validate environment configuration before starting Docker services
# Checks required variables, URL formats, and configuration consistency
#
# Usage:
#   bash backend/scripts/validate_env.sh [path/to/.env.production]
#
# Exit codes:
#   0 - validation passed
#   1 - validation failed

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1" >&2; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
info() { echo "ℹ $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${1:-$BACKEND_DIR/.env.production}"
WORKER_ENV_VALIDATION_FILE="${VALIDATE_WORKER_ENV_FILE:-${WORKER_ENV_FILE:-$ENV_FILE}}"
EFFECTIVE_TIER1="${VALIDATE_EFFECTIVE_TIER1:-auto}"
EFFECTIVE_LINUX_MLX="${VALIDATE_EFFECTIVE_LINUX_MLX:-auto}"

ERRORS=0
WARNINGS=0

info "Validating environment configuration: $ENV_FILE"
echo ""

# ============================================================================
# Check file exists
# ============================================================================
if [ ! -f "$ENV_FILE" ]; then
  fail "Environment file not found: $ENV_FILE"
  exit 1
fi
pass "Environment file exists"

# ============================================================================
# Required variables check
# ============================================================================
info "Checking required variables..."

check_required() {
  check_required_in_file "$ENV_FILE" "$1" "$2"
}

check_required_in_file() {
  local source_file="$1"
  local var_name="$2"
  local description="$3"

  if ! grep -qE "^${var_name}=.+" "$source_file"; then
    fail "$description ($var_name) is not set or empty"
    ERRORS=$((ERRORS + 1))
    return 1
  fi

  # Check it's not a placeholder
  local value
  value="$(get_value_from_file "$source_file" "$var_name")"
  if [[ "$value" == "change-me" ]] || [[ "$value" == "your-"* ]] || [[ "$value" == "REPLACE_"* ]] || [[ "$value" == "replace_"* ]] || [[ "$value" == "<"*">" ]]; then
    fail "$description ($var_name) contains placeholder value: $value"
    ERRORS=$((ERRORS + 1))
    return 1
  fi

  pass "$description"
  return 0
}

get_value_from_file() {
  local source_file="$1"
  local var_name="$2"
  [ -f "$source_file" ] || return 0
  grep -E "^${var_name}=" "$source_file" | tail -n1 | cut -d'=' -f2- | tr -d '\r' | tr -d '"' | tr -d "'" || true
}

detect_host_platform() {
  if [ -n "${VALIDATE_HOST_PLATFORM:-}" ]; then
    echo "$VALIDATE_HOST_PLATFORM"
    return
  fi

  if [ -f /proc/version ] && grep -qi microsoft /proc/version 2>/dev/null; then
    echo "wsl"
    return
  fi

  case "$(uname -s 2>/dev/null | tr '[:upper:]' '[:lower:]')" in
    linux*) echo "linux" ;;
    *) echo "other" ;;
  esac
}

file_has_true() {
  local source_file="$1"
  local var_name="$2"
  [ "$(get_value_from_file "$source_file" "$var_name")" = "true" ]
}

EFFECTIVE_TIER1_ENABLED=0
EFFECTIVE_LINUX_MLX_ENABLED=0
HOST_PLATFORM="$(detect_host_platform)"

if [ "$EFFECTIVE_TIER1" = "true" ] || file_has_true "$ENV_FILE" "ENABLE_TIER1" || file_has_true "$WORKER_ENV_VALIDATION_FILE" "ENABLE_TIER1"; then
  EFFECTIVE_TIER1_ENABLED=1
fi

if [ "$EFFECTIVE_LINUX_MLX" = "true" ] || file_has_true "$ENV_FILE" "ENABLE_LINUX_MLX" || file_has_true "$WORKER_ENV_VALIDATION_FILE" "ENABLE_LINUX_MLX"; then
  EFFECTIVE_LINUX_MLX_ENABLED=1
  EFFECTIVE_TIER1_ENABLED=1
fi

if [ "$EFFECTIVE_TIER1_ENABLED" -eq 1 ]; then
  if [ ! -f "$WORKER_ENV_VALIDATION_FILE" ]; then
    fail "Worker env file not found: $WORKER_ENV_VALIDATION_FILE"
    ERRORS=$((ERRORS + 1))
  else
    pass "Worker env file exists"
  fi
fi

if [ "$HOST_PLATFORM" = "linux" ] && [ "$EFFECTIVE_TIER1_ENABLED" -eq 1 ] && [ "$EFFECTIVE_LINUX_MLX_ENABLED" -eq 0 ]; then
  fail "Effective Tier 1 on real Linux requires ENABLE_LINUX_MLX=true (or start_production.sh --with-linux-mlx); docker-compose.tier1.yml is diagnostic-only for WSL2/Windows"
  ERRORS=$((ERRORS + 1))
fi

# Core required variables
check_required "API_TOKEN" "API authentication token"
check_required "DATABASE_URL" "Database URL"
check_required "REDIS_URL" "Redis URL"
check_required "POSTGRES_USER" "PostgreSQL user"
check_required "POSTGRES_PASSWORD" "PostgreSQL password"
check_required "POSTGRES_DB" "PostgreSQL database name"

echo ""

# ============================================================================
# URL format validation
# ============================================================================
info "Validating URL formats..."

check_url_format() {
  local var_name="$1"
  local description="$2"
  local expected_host="$3"  # Expected hostname (e.g., "postgres", "redis", "127.0.0.1")

  if ! grep -qE "^${var_name}=" "$ENV_FILE"; then
    warn "$description ($var_name) not set"
    WARNINGS=$((WARNINGS + 1))
    return 1
  fi

  local value
  value="$(get_value_from_file "$ENV_FILE" "$var_name")"

  # Check for expected host in URL
  if [[ -n "$expected_host" ]] && ! echo "$value" | grep -q "$expected_host"; then
    warn "$description should use '$expected_host' for bridge network (current: $value)"
    WARNINGS=$((WARNINGS + 1))
    return 1
  fi

  pass "$description"
  return 0
}

# Bridge network URLs (should use service names)
check_url_format "DATABASE_URL" "Database URL" "postgres"
check_url_format "REDIS_URL" "Redis URL" "redis"
check_url_format "EMAIL_VERIFIER_URL" "Email verifier URL" "email-verifier"
check_url_format "SOCIAL_ANALYZER_URL" "Social analyzer URL" "social-analyzer"
check_url_format "GMAPS_SCRAPER_URL" "Google Maps scraper URL" "google-maps-scraper"

echo ""

# ============================================================================
# Worker queue mode validation
# ============================================================================
info "Checking worker configuration..."

if grep -qE "^WORKER_QUEUE_MODE=per_tier" "$ENV_FILE"; then
  pass "Worker queue mode set to 'per_tier'"
else
  fail "WORKER_QUEUE_MODE must be 'per_tier' for tier-specific workers"
  ERRORS=$((ERRORS + 1))
fi

if grep -qE "^OUTREACH_ENABLED=false" "$ENV_FILE"; then
  info "Outreach disabled (skipping physical-address requirement)"
else
  check_required "OUTREACH_PHYSICAL_ADDRESS" "Outreach physical mailing address"
fi

echo ""

# ============================================================================
# Tier 1 configuration validation
# ============================================================================
if [ "$EFFECTIVE_TIER1_ENABLED" -eq 1 ]; then
  info "Tier 1 effective runtime enabled - checking worker-tier1 configuration..."
  info "Worker env source: $WORKER_ENV_VALIDATION_FILE"

  if [ -f "$WORKER_ENV_VALIDATION_FILE" ]; then
    check_required_in_file "$WORKER_ENV_VALIDATION_FILE" "MULTILOGIN_EMAIL" "Multilogin email"
    check_required_in_file "$WORKER_ENV_VALIDATION_FILE" "MULTILOGIN_PASSWORD" "Multilogin password"
    check_required_in_file "$WORKER_ENV_VALIDATION_FILE" "MULTILOGIN_FOLDER_ID" "Multilogin folder ID"
    check_required_in_file "$WORKER_ENV_VALIDATION_FILE" "LINKEDIN_BOT_EMAIL" "LinkedIn bot email"
    check_required_in_file "$WORKER_ENV_VALIDATION_FILE" "LINKEDIN_BOT_PASSWORD" "LinkedIn bot password"

    browser_mode="$(get_value_from_file "$WORKER_ENV_VALIDATION_FILE" "BROWSER_MODE")"
    if [ -z "$browser_mode" ]; then
      pass "BROWSER_MODE defaults to multilogin for worker-tier1"
    elif [ "$browser_mode" = "multilogin" ]; then
      pass "BROWSER_MODE is multilogin for worker-tier1"
    else
      fail "BROWSER_MODE must be 'multilogin' for effective Tier 1 runtime (current: $browser_mode)"
      ERRORS=$((ERRORS + 1))
    fi

    if [ "$EFFECTIVE_LINUX_MLX_ENABLED" -eq 1 ]; then
      info "Linux containerized Multilogin target detected"
      check_required_in_file "$ENV_FILE" "AWS_ACCESS_KEY_ID" "AWS access key ID"
      check_required_in_file "$ENV_FILE" "AWS_SECRET_ACCESS_KEY" "AWS secret access key"
    fi
  fi

  echo ""
else
  info "Tier 1 disabled (skipping LinkedIn configuration)"
  echo ""
fi

# ============================================================================
# Proxy configuration validation
# ============================================================================
if grep -qE "^PROXY_MODE=paid" "$ENV_FILE"; then
  info "Paid proxy mode enabled - checking configuration..."

  check_required "SCRAPOXY_URL" "Proxy URL"
  check_required "SCRAPOXY_USERNAME" "Proxy username"
  check_required "SCRAPOXY_PASSWORD" "Proxy password"

  echo ""
fi

# ============================================================================
# LLM configuration validation
# ============================================================================
if grep -qE "^LLM_MODE=litellm" "$ENV_FILE"; then
  info "LiteLLM mode enabled - checking configuration..."

  # Check that API keys are set
  has_openai=$(grep -qE "^OPENAI_API_KEY=.+" "$ENV_FILE" && echo "true" || echo "false")
  has_gemini=$(grep -qE "^GEMINI_API_KEY=.+" "$ENV_FILE" && echo "true" || echo "false")

  if [[ "$has_openai" == "false" ]] && [[ "$has_gemini" == "false" ]]; then
    warn "No LLM API keys set (OPENAI_API_KEY or GEMINI_API_KEY)"
    WARNINGS=$((WARNINGS + 1))
  else
    pass "LLM API keys configured"
  fi

  echo ""
fi

# ============================================================================
# Storage configuration
# ============================================================================
if [ "$EFFECTIVE_TIER1_ENABLED" -eq 1 ]; then
  info "Checking R2 storage configuration (required for Tier 1)..."

  if [ -f "$WORKER_ENV_VALIDATION_FILE" ]; then
    check_required_in_file "$WORKER_ENV_VALIDATION_FILE" "R2_ACCOUNT_ID" "R2 account ID"
    check_required_in_file "$WORKER_ENV_VALIDATION_FILE" "R2_ACCESS_KEY_ID" "R2 access key ID"
    check_required_in_file "$WORKER_ENV_VALIDATION_FILE" "R2_SECRET_ACCESS_KEY" "R2 secret access key"
    check_required_in_file "$WORKER_ENV_VALIDATION_FILE" "R2_BUCKET" "R2 bucket name"
    check_required_in_file "$WORKER_ENV_VALIDATION_FILE" "R2_PUBLIC_BASE_URL" "R2 public base URL"
  fi

  echo ""
fi

# ============================================================================
# Security checks
# ============================================================================
info "Running security checks..."

# Check for weak passwords (common patterns)
if grep -qE "^POSTGRES_PASSWORD=(password|123456|admin|postgres)" "$ENV_FILE"; then
  fail "PostgreSQL password appears to be weak or default"
  ERRORS=$((ERRORS + 1))
else
  pass "PostgreSQL password appears secure"
fi

# Check API token length
api_token="$(get_value_from_file "$ENV_FILE" "API_TOKEN")"
if [ ${#api_token} -lt 32 ]; then
  warn "API_TOKEN should be at least 32 characters long"
  WARNINGS=$((WARNINGS + 1))
else
  pass "API token length is adequate"
fi

echo ""

# ============================================================================
# Network mode consistency check
# ============================================================================
info "Checking network configuration consistency..."

# Check if any URLs use 127.0.0.1 (should be rare, only for tier1 overrides)
# Fixed: Use simpler grep without greedy .* to avoid backtracking hang
localhost_urls="$(grep -c "127\.0\.0\.1" "$ENV_FILE" 2>/dev/null || true)"
localhost_urls="${localhost_urls:-0}"

if [ "$localhost_urls" -gt 0 ]; then
  warn "Found $localhost_urls URL(s) using 127.0.0.1 - ensure this is intentional"
  warn "Bridge network services should use service names (postgres, redis, etc.)"
  warn "Only Tier 1 worker overrides should use 127.0.0.1"
  WARNINGS=$((WARNINGS + 1))
else
  pass "All URLs use appropriate hostnames"
fi

echo ""

# ============================================================================
# Summary
# ============================================================================
echo "════════════════════════════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then
  if [ $WARNINGS -eq 0 ]; then
    pass "Validation passed with no errors or warnings"
    echo "════════════════════════════════════════════════════════════"
    exit 0
  else
    warn "Validation passed with $WARNINGS warning(s)"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    info "You can proceed, but review the warnings above"
    exit 0
  fi
else
  fail "Validation failed with $ERRORS error(s) and $WARNINGS warning(s)"
  echo "════════════════════════════════════════════════════════════"
  echo ""
  info "Fix the errors above before starting the infrastructure"
  exit 1
fi
