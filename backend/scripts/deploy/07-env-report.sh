#!/usr/bin/env bash
# 07-env-report.sh — classify all §12 inventory keys in the env file.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

STATUS_FILE="${ENV_FILE}.status"
PLAN="$REPO_ROOT/plan.md"

placeholder() {
  local v="$1"
  [[ -z "$v" ]] && return 1
  case "$v" in
    REPLACE_*|replace_*|change-me*|changeme*|your-*|Your-*|pplx-*|*example.com*|*cdn-staging*) return 0 ;;
  esac
  # angle-bracket placeholders like <YOUR_TOKEN>
  [[ "$v" == \<*\> ]] && return 0
  return 1
}

declare -A FILE_STATUS=()
if [[ -f "$STATUS_FILE" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    k="${line%%=*}"
    v="${line#*=}"
    FILE_STATUS["$k"]="$v"
  done < "$STATUS_FILE"
fi

DEFERRED_KEYS=(
  MULTILOGIN_API_URL MULTILOGIN_LAUNCHER_URL MULTILOGIN_EMAIL MULTILOGIN_PASSWORD
  MULTILOGIN_FOLDER_ID MULTILOGIN_WORKSPACE_ID MULTILOGIN_PROFILE_ID
  MULTILOGIN_PROFILE_POOL_SIZE MULTILOGIN_DAILY_VIEW_LIMIT
  MULTILOGIN_PROFILE_COOLDOWN_SECONDS MULTILOGIN_RATE_LIMIT_COOLDOWN_SECONDS
  MULTILOGIN_SELENIUM_HOST MULTILOGIN_CDP_URL MULTILOGIN_HOST_IP
  LINKEDIN_BOT_EMAIL LINKEDIN_BOT_PASSWORD
  TIER1_BROWSER_TIMEOUT_SECONDS TIER1_MAX_CONCURRENT_BROWSERS
  TIER1_SKIP_LOGIN_IF_SESSION_VALID TIER1_PLACEHOLDER_DENYLIST
  WORKER_ENV_FILE API_ENV_FILE
  AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
  STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET STRIPE_PRICE_ID_PREMIUM STRIPE_API_BASE
)

is_deferred() {
  local k="$1"
  if [[ "$(env_get ENABLE_TIER1)" != "true" ]]; then
    for d in "${DEFERRED_KEYS[@]}"; do
      [[ "$k" == "$d" ]] && return 0
    done
  fi
  return 1
}

mapfile -t KEYS < <(python3 - <<PY
import re
from pathlib import Path
text = Path("$PLAN").read_text()
m = re.search(r"## 12\\. Master environment inventory(.*?)## 13\\.", text, re.S)
skip = {"HS256","INFO","BACKEND_API_URL","BACKEND_API_TOKEN","BACKEND_FETCH_TIMEOUT_MS",
        "FRONTEND_USE_MOCKS","NEXT_PUBLIC_VAPID_PUBLIC_KEY","PORTFOLIO_SUBDOMAINS_ENABLED",
        "PORTFOLIO_SUBDOMAIN_ROOT"}
seen=set(); keys=[]
for k in re.findall(r"\`([A-Z][A-Z0-9_]+)\`", m.group(1)):
    if k in skip or k in seen: continue
    seen.add(k); keys.append(k)
print("\\n".join(keys))
PY
)

printf "%-48s %s\n" "KEY" "STATUS"
printf "%-48s %s\n" "-----------------------------------------------" "------"
counts_ok=0; counts_empty=0; counts_ph=0; counts_exp=0; counts_need=0; counts_def=0; counts_miss=0

for k in "${KEYS[@]}"; do
  if ! grep -qE "^${k}=" "$ENV_FILE"; then
    printf "%-48s %s\n" "$k" "MISSING"
    counts_miss=$((counts_miss+1))
    continue
  fi
  v="$(env_get "$k")"
  mark="${FILE_STATUS[$k]:-}"
  status=""
  if [[ -n "$mark" ]]; then
    status="$mark"
  elif is_deferred "$k"; then
    status="DEFERRED"
  elif [[ -z "$v" ]]; then
    status="EMPTY"
  elif placeholder "$v"; then
    status="PLACEHOLDER"
  else
    status="OK"
  fi
  case "$status" in
    OK) counts_ok=$((counts_ok+1)) ;;
    EMPTY) counts_empty=$((counts_empty+1)) ;;
    PLACEHOLDER) counts_ph=$((counts_ph+1)); status="PLACEHOLDER / NEED_LATER" ; counts_need=$((counts_need+1)) ;;
    EXPIRED) counts_exp=$((counts_exp+1)) ;;
    NEED_LATER) counts_need=$((counts_need+1)) ;;
    DEFERRED) counts_def=$((counts_def+1)) ;;
  esac
  printf "%-48s %s\n" "$k" "$status"
done

echo
echo "Summary: OK=$counts_ok EMPTY=$counts_empty PLACEHOLDER/NEED_LATER=$counts_need EXPIRED=$counts_exp DEFERRED=$counts_def MISSING=$counts_miss"
echo "Env file: $ENV_FILE"
