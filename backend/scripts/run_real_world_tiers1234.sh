#!/usr/bin/env bash
# Real-world Tier 1-4 run: brings up the real compose stack (real sidecars,
# real CLIs, real Multilogin), runs Tier 2-4 then Tier 1 against it, and
# combines both stage reports (with per-enricher timing) into one JSON report.
#
# Stage A (Tier 2-4): docker compose exec -T api probe_enrichers.py --canary
#   against real Sherlock/Maigret/GitRecon/TheHarvester/CrossLinked CLIs plus
#   real social-analyzer / email-verifier / google-maps-scraper sidecars.
# Stage B (Tier 1): scripts/e2e_tier1_canary.py run from the WSL host (venv
#   created on first use) through POST /enrich -> RQ worker -> real Multilogin
#   X launcher on the Windows host -> real LinkedIn. Single pass, no retries
#   (Multilogin daily view budget is limited).
#
# Usage:
#   bash backend/scripts/run_real_world_tiers1234.sh
#
# Requires Docker in WSL (Ubuntu). On Windows, invoke via:
#   wsl -d Ubuntu bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/run_real_world_tiers1234.sh
#
# Env:
#   E2E_KEEP_STACK=1   leave the compose stack up after the run
#   GITHUB_TOKEN       should already be set in backend/.env (raises GitRecon /
#                      TheHarvester GitHub API rate limits)
#
# Report: backend/.e2e-results/real-world-tiers1234-report.json
# Exit: non-zero if either stage fails.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$BACKEND_DIR/.env"
RESULTS_DIR="$BACKEND_DIR/.e2e-results"
REPORT="$RESULTS_DIR/real-world-tiers1234-report.json"
BASE="http://localhost:8000"
COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.tier1.yml)

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1" >&2; exit 1; }
warn() { echo "WARN  $1"; }

mkdir -p "$RESULTS_DIR"

if [ ! -f "$ENV_FILE" ]; then
  fail "backend/.env not found - populate real sidecar/Multilogin/GitHub settings before a real-world run"
fi

cleanup() {
  if [ "${E2E_KEEP_STACK:-0}" != "1" ]; then
    (cd "$COMPOSE_DIR" && docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" down)
  fi
}
trap cleanup EXIT

RUN_START="$(date +%s)"

# WSL2 + Docker Engine (unlike Docker Desktop): `host-gateway` in extra_hosts
# resolves to the WSL VM, not the Windows host running Multilogin X. Auto-detect
# the Windows host via the WSL default route unless already set (see
# docker-compose.tier1.yml).
if [ -z "${MULTILOGIN_HOST_IP:-}" ] && [ -f /proc/version ] && grep -qi microsoft /proc/version 2>/dev/null; then
  detected_host_ip="$(ip route show default 2>/dev/null | awk '{print $3}' | head -n1)"
  if [ -n "$detected_host_ip" ]; then
    export MULTILOGIN_HOST_IP="$detected_host_ip"
    warn "auto-detected MULTILOGIN_HOST_IP=$MULTILOGIN_HOST_IP (WSL2 default route to Windows host)"
  fi
fi

echo "== bring up real stack (api, worker w/ tier1, redis, postgres, sidecars) =="
cd "$COMPOSE_DIR"
docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" up --build -d \
  migrate api worker redis postgres social-analyzer google-maps-scraper email-verifier

echo "== wait for API health =="
for i in $(seq 1 90); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health" || true)"
  [ "$code" = "200" ] && break
  sleep 3
done
[ "$code" = "200" ] || fail "API health never returned 200 (last=$code)"
pass "api health 200"

echo "== wait for social-analyzer =="
for i in $(seq 1 60); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:9005/get_settings || true)"
  [ "$code" = "200" ] && break
  sleep 5
done
[ "$code" = "200" ] || fail "social-analyzer /get_settings never returned 200 (last=$code)"
pass "social-analyzer ready"

echo "== wait for google-maps-scraper =="
for i in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/api/docs || true)"
  [ "$code" = "200" ] && break
  sleep 3
done
[ "$code" = "200" ] || fail "gmaps /api/docs never returned 200 (last=$code)"
pass "google-maps-scraper ready"

echo "== wait for email-verifier =="
for i in $(seq 1 60); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8081/v1/health@example.com/verification" || true)"
  [ "$code" = "200" ] && break
  sleep 5
done
[ "$code" = "200" ] || fail "email-verifier never returned 200 (last=$code)"
pass "email-verifier ready"

echo "== wait for worker (Tier 1 enabled) =="
for i in $(seq 1 30); do
  if docker compose --env-file "$ENV_FILE" exec -T worker true 2>/dev/null; then
    break
  fi
  sleep 2
done
docker compose --env-file "$ENV_FILE" exec -T worker true 2>/dev/null \
  || fail "worker is not running (check ENABLE_TIER1 / Multilogin settings)"
pass "worker running"

echo "== worker CLIs (tier 2/3) =="
docker compose --env-file "$ENV_FILE" exec -T worker sh -c '
  which sherlock
  which maigret
  which theHarvester
  which crosslinked
  which email-sleuth
  test -f "${GITRECON_SCRIPT:-/opt/gitrecon/gitrecon.py}"
'
pass "worker has tier 2/3 CLIs"

# â”€â”€ Stage A: Tier 2-4 real-sidecar canary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
STAGE_A_START="$(date +%s)"
STAGE_A_EXIT=0

echo ""
echo "========== Stage A: Tier 2-4 canary (real CLIs + real sidecars) =========="
docker compose --env-file "$ENV_FILE" exec -T api sh -c 'mkdir -p /app/backend/docs' \
  < /dev/null
docker compose --env-file "$ENV_FILE" exec -T api sh -c 'cat > /app/backend/docs/tier234_canary_set.json' \
  < "$BACKEND_DIR/docs/tier234_canary_set.json"

set +e
docker compose --env-file "$ENV_FILE" exec -T api sh -c '
  set -e
  export E2E_BASE_URL=http://127.0.0.1:8000
  export SOCIAL_ANALYZER_URL=http://social-analyzer:9005
  export GMAPS_SCRAPER_URL=http://google-maps-scraper:8080
  export EMAIL_VERIFIER_URL=http://email-verifier:8080
  export GITRECON_SCRIPT=/opt/gitrecon/gitrecon.py
  export GMAPS_JOB_TIMEOUT_SECONDS="${GMAPS_JOB_TIMEOUT_SECONDS:-300}"
  export GMAPS_JOB_POLL_SECONDS="${GMAPS_JOB_POLL_SECONDS:-10}"
  export E2E_BACKEND_ROOT=/app/backend
  cd /app/backend
  mkdir -p /app/backend/.e2e-results
  test -f "${GITRECON_SCRIPT}"
  python - --canary docs/tier234_canary_set.json --json
' < "$SCRIPT_DIR/probe_enrichers.py"
STAGE_A_EXIT=$?
set -e

STAGE_A_END="$(date +%s)"
STAGE_A_DURATION=$((STAGE_A_END - STAGE_A_START))

docker compose --env-file "$ENV_FILE" exec -T api cat /app/backend/.e2e-results/tier234-canary.json \
  > "$RESULTS_DIR/tier234-canary.json" || true

if [ "$STAGE_A_EXIT" -eq 0 ]; then
  pass "Stage A Tier 2-4 canary (${STAGE_A_DURATION}s)"
else
  warn "Stage A Tier 2-4 canary FAILED (exit=$STAGE_A_EXIT, ${STAGE_A_DURATION}s) - continuing to Stage B"
fi

# â”€â”€ Stage B: Tier 1 full API+worker canary (real Multilogin/LinkedIn) â”€â”€
STAGE_B_START="$(date +%s)"
STAGE_B_EXIT=0

echo ""
echo "========== Stage B: Tier 1 canary (real Multilogin + LinkedIn, full API+worker path) =========="

VENV_DIR="$BACKEND_DIR/.venv-wsl"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "== creating WSL-side venv for host-side Tier 1 canary run =="
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --quiet --upgrade pip
  "$VENV_DIR/bin/pip" install --quiet -e "$BACKEND_DIR"
fi

set +e
(
  cd "$BACKEND_DIR"
  "$VENV_DIR/bin/python" scripts/e2e_tier1_canary.py \
    --file docs/tier1_canary_set.json \
    --base-url "$BASE" \
    --json
)
STAGE_B_EXIT=$?
set -e

STAGE_B_END="$(date +%s)"
STAGE_B_DURATION=$((STAGE_B_END - STAGE_B_START))

if [ "$STAGE_B_EXIT" -eq 0 ]; then
  pass "Stage B Tier 1 canary (${STAGE_B_DURATION}s)"
else
  warn "Stage B Tier 1 canary FAILED (exit=$STAGE_B_EXIT, ${STAGE_B_DURATION}s)"
fi

RUN_END="$(date +%s)"
TOTAL_DURATION=$((RUN_END - RUN_START))

# â”€â”€ Combine both stage reports + timing into one report â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
STAGE_A_EXIT="$STAGE_A_EXIT" STAGE_A_DURATION="$STAGE_A_DURATION" \
STAGE_B_EXIT="$STAGE_B_EXIT" STAGE_B_DURATION="$STAGE_B_DURATION" \
TOTAL_DURATION="$TOTAL_DURATION" \
RESULTS_DIR="$RESULTS_DIR" REPORT="$REPORT" \
python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

results_dir = Path(os.environ["RESULTS_DIR"])
report_path = Path(os.environ["REPORT"])


def load(name: str) -> dict:
    path = results_dir / name
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


tier234 = load("tier234-canary.json")
tier1 = load("tier1-api-canary.json")

tier234_summary = tier234.get("summary", {})
tier1_summary = tier1.get("summary", {})

timing_by_enricher = dict(tier234.get("timing_by_enricher", {}))
tier1_durations = [
    row["duration_seconds"]
    for row in tier1.get("rows", [])
    if row.get("duration_seconds")
]
if tier1_durations:
    timing_by_enricher["linkedin_photo"] = {
        "count": len(tier1_durations),
        "min_seconds": round(min(tier1_durations), 3),
        "avg_seconds": round(sum(tier1_durations) / len(tier1_durations), 3),
        "max_seconds": round(max(tier1_durations), 3),
        "total_seconds": round(sum(tier1_durations), 3),
    }

report = {
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "stages": [
        {
            "name": "tier2-4",
            "script": "probe_enrichers.py --canary docs/tier234_canary_set.json",
            "exit_code": int(os.environ["STAGE_A_EXIT"]),
            "duration_seconds": int(os.environ["STAGE_A_DURATION"]),
            "summary": tier234_summary,
        },
        {
            "name": "tier1",
            "script": "e2e_tier1_canary.py --file docs/tier1_canary_set.json",
            "exit_code": int(os.environ["STAGE_B_EXIT"]),
            "duration_seconds": int(os.environ["STAGE_B_DURATION"]),
            "summary": tier1_summary,
        },
    ],
    "timing_by_enricher": timing_by_enricher,
    "total_duration_seconds": int(os.environ["TOTAL_DURATION"]),
}
report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"\nCombined report: {report_path}")
print(
    "Summary: "
    f"tier2-4 exit={report['stages'][0]['exit_code']} "
    f"tier1 exit={report['stages'][1]['exit_code']} "
    f"total_duration={report['total_duration_seconds']}s"
)
PY

if [ "$STAGE_A_EXIT" -ne 0 ] || [ "$STAGE_B_EXIT" -ne 0 ]; then
  exit 1
fi

echo ""
echo "All real-world Tier 1-4 checks passed."
echo "Report: $REPORT"
