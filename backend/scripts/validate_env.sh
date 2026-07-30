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
  local var_name="$1"
  local description="$2"

  if ! grep -qE "^${var_name}=.+" "$ENV_FILE"; then
    fail "$description ($var_name) is not set or empty"
    ERRORS=$((ERRORS + 1))
    return 1
  fi

  # Check it's not a placeholder
  local value=$(grep -E "^${var_name}=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
  if [[ "$value" == "change-me" ]] || [[ "$value" == "your-"* ]] || [[ "$value" == "<"*">" ]]; then
    fail "$description ($var_name) contains placeholder value: $value"
    ERRORS=$((ERRORS + 1))
    return 1
  fi

  pass "$description"
  return 0
}

# Core required variables
check_required "API_TOKEN" "API authentication token"
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

  local value=$(grep -E "^${var_name}=" "$ENV_FILE" | cut -d'=' -f2-)

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

echo ""

# ============================================================================
# Tier 1 configuration validation
# ============================================================================
if grep -qE "^ENABLE_TIER1=true" "$ENV_FILE"; then
  info "Tier 1 enabled - checking required configuration..."

  check_required "MULTILOGIN_EMAIL" "Multilogin email"
  check_required "MULTILOGIN_PASSWORD" "Multilogin password"
  check_required "MULTILOGIN_FOLDER_ID" "Multilogin folder ID"
  check_required "MULTILOGIN_WORKSPACE_ID" "Multilogin workspace ID"
  check_required "LINKEDIN_BOT_EMAIL" "LinkedIn bot email"
  check_required "LINKEDIN_BOT_PASSWORD" "LinkedIn bot password"

  # Check for Linux MLX mode
  if grep -qE "^ENABLE_LINUX_MLX=true" "$ENV_FILE"; then
    info "Linux containerized Multilogin mode detected"

    # Check AWS credentials if needed (for build time)
    if ! grep -qE "^AWS_ACCESS_KEY_ID=.+" "$ENV_FILE"; then
      warn "AWS_ACCESS_KEY_ID not set (needed for building Linux MLX image)"
      WARNINGS=$((WARNINGS + 1))
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
if grep -qE "^ENABLE_TIER1=true" "$ENV_FILE"; then
  info "Checking R2 storage configuration (required for Tier 1)..."

  check_required "R2_ACCOUNT_ID" "R2 account ID"
  check_required "R2_ACCESS_KEY_ID" "R2 access key ID"
  check_required "R2_SECRET_ACCESS_KEY" "R2 secret access key"
  check_required "R2_BUCKET" "R2 bucket name"
  check_required "R2_PUBLIC_BASE_URL" "R2 public base URL"

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
api_token=$(grep -E "^API_TOKEN=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
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
localhost_urls=$(grep -c "127\.0\.0\.1" "$ENV_FILE" 2>/dev/null || echo "0")

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
