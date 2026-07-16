#!/usr/bin/env bash
# Full-path E2E runner: chains existing compose / fake-sidecar / live tier scripts.
#
# Modes:
#   --ci   (default)  e2e_compose_test.sh → e2e_fake_sidecars.sh
#   --live            probe_sidecars.sh → e2e_tier2.sh → e2e_tier3.sh → e2e_realworld_strict.sh
#   --all             --ci then --live
#
# Usage:
#   bash backend/scripts/e2e_full_path.sh [--ci|--live|--all]
#
# Env:
#   E2E_SKIP_COMPOSE=1   skip e2e_compose_test.sh when stack already up (--ci / --all)
#   E2E_KEEP_STACK=1     leave compose stacks up after child scripts (forwarded)
#
# Report: backend/.e2e-results/full-path-report.json
# Exit: non-zero if any stage fails.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTS_DIR="$BACKEND_DIR/.e2e-results"
REPORT="$RESULTS_DIR/full-path-report.json"

MODE="${1:---ci}"
case "$MODE" in
  --ci|--live|--all) ;;
  -h|--help)
    sed -n '2,18p' "$0"
    exit 0
    ;;
  *)
    echo "Unknown mode: $MODE (use --ci, --live, or --all)" >&2
    exit 2
    ;;
esac

mkdir -p "$RESULTS_DIR"

declare -a STAGE_NAMES=()
declare -a STAGE_SCRIPTS=()

add_stage() {
  STAGE_NAMES+=("$1")
  STAGE_SCRIPTS+=("$2")
}

case "$MODE" in
  --ci)
    add_stage compose_test "$SCRIPT_DIR/e2e_compose_test.sh"
    add_stage fake_sidecars "$SCRIPT_DIR/e2e_fake_sidecars.sh"
    ;;
  --live)
    add_stage probe_sidecars "$SCRIPT_DIR/probe_sidecars.sh"
    add_stage tier2 "$SCRIPT_DIR/e2e_tier2.sh"
    add_stage tier3 "$SCRIPT_DIR/e2e_tier3.sh"
    add_stage realworld_strict "$SCRIPT_DIR/e2e_realworld_strict.sh"
    ;;
  --all)
    add_stage compose_test "$SCRIPT_DIR/e2e_compose_test.sh"
    add_stage fake_sidecars "$SCRIPT_DIR/e2e_fake_sidecars.sh"
    add_stage probe_sidecars "$SCRIPT_DIR/probe_sidecars.sh"
    add_stage tier2 "$SCRIPT_DIR/e2e_tier2.sh"
    add_stage tier3 "$SCRIPT_DIR/e2e_tier3.sh"
    add_stage realworld_strict "$SCRIPT_DIR/e2e_realworld_strict.sh"
    ;;
esac

overall_fail=0
passed=0
failed=0
skip_count=0
declare -a STAGE_RECORDS=()

child_report_for() {
  case "$1" in
    fake_sidecars) echo "fake-sidecars-report.json" ;;
    tier2) echo "tier2-report.json" ;;
    tier3) echo "tier3-report.json" ;;
    realworld_strict) echo "strict-report.json" ;;
    *) echo "" ;;
  esac
}

run_stage() {
  local name="$1"
  local script="$2"
  local was_skipped=false
  local skip_reason=""
  local exit_code=0
  local duration=0

  if [ "$name" = "compose_test" ] && [ "${E2E_SKIP_COMPOSE:-0}" = "1" ]; then
    was_skipped=true
    skip_reason="E2E_SKIP_COMPOSE=1"
    echo "SKIP  $name ($skip_reason)"
    skip_count=$((skip_count + 1))
    passed=$((passed + 1))
  else
    echo ""
    echo "========== stage: $name ($script) =========="
    local start end
    start="$(date +%s)"
    set +e
    bash "$script"
    exit_code=$?
    set -e
    end="$(date +%s)"
    duration=$((end - start))
    if [ "$exit_code" -eq 0 ]; then
      echo "PASS  $name (exit=$exit_code, ${duration}s)"
      passed=$((passed + 1))
    else
      echo "FAIL  $name (exit=$exit_code, ${duration}s)" >&2
      failed=$((failed + 1))
      overall_fail=1
    fi
  fi

  local child_report
  child_report="$(child_report_for "$name")"
  STAGE_RECORDS+=("$(
    MODE_NAME="$name" \
    MODE_SCRIPT="$(basename "$script")" \
    MODE_EXIT="$exit_code" \
    MODE_DURATION="$duration" \
    MODE_SKIPPED="$was_skipped" \
    MODE_SKIP_REASON="$skip_reason" \
    MODE_CHILD="$child_report" \
    python3 - <<'PY'
import json, os
name = os.environ["MODE_NAME"]
skipped = os.environ["MODE_SKIPPED"] == "true"
exit_code = int(os.environ["MODE_EXIT"])
print(json.dumps({
    "name": name,
    "script": os.environ["MODE_SCRIPT"],
    "ok": skipped or exit_code == 0,
    "exit_code": exit_code,
    "duration_seconds": float(os.environ["MODE_DURATION"]),
    "skipped": skipped,
    "skip_reason": os.environ["MODE_SKIP_REASON"] or None,
    "child_report": os.environ["MODE_CHILD"] or None,
}))
PY
  )")
}

for i in "${!STAGE_NAMES[@]}"; do
  run_stage "${STAGE_NAMES[$i]}" "${STAGE_SCRIPTS[$i]}"
done

python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path

records = [json.loads(line) for line in """$(printf '%s\n' "${STAGE_RECORDS[@]}")""".splitlines() if line.strip()]
report = {
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "mode": "${MODE#--}",
    "stages": records,
    "passed": $passed,
    "failed": $failed,
    "skipped": $skip_count,
}
path = Path("""$REPORT""")
path.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"\nFull-path report: {path}")
print(f"Summary: {report['passed']} passed, {report['failed']} failed, {report['skipped']} skipped")
PY

exit "$overall_fail"
