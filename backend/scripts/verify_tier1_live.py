"""Tier 1 live proof runner (Task 13 / M3).

Chains the proof sequence from backend/docs/TESTING_TIER1.md and writes
backend/.e2e-results/verify-tier1-live.json.

Usage:
  cd backend
  python scripts/verify_tier1_live.py
  python scripts/verify_tier1_live.py --skip-live   # shape + prereqs only
  python scripts/verify_tier1_live.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / ".e2e-results"
REPORT = RESULTS / "verify-tier1-live.json"
CANARY = ROOT / "docs" / "tier1_canary_set.json"
PLACEHOLDER_RE = re.compile(r"your-[a-z0-9-]*-slug", re.I)


@dataclass
class StepResult:
    name: str
    command: str
    exit_code: int
    status: str
    detail: str = ""


def _run(cmd: list[str], *, cwd: Path = ROOT) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def canary_filled() -> tuple[bool, str]:
    if not CANARY.is_file():
        return False, f"missing {CANARY.name} — copy tier1_canary_set.example.json and fill"
    text = CANARY.read_text(encoding="utf-8")
    if PLACEHOLDER_RE.search(text):
        return False, "tier1_canary_set.json still contains placeholder slugs (your-*-slug)"
    return True, "canary file present"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Tier 1 live proof matrix")
    parser.add_argument("--skip-live", action="store_true", help="Skip MLX/canary live steps")
    parser.add_argument("--json", action="store_true", help="Print report JSON to stdout")
    parser.add_argument("--limit", type=int, default=None, help="Canary row limit")
    args = parser.parse_args()

    steps: list[StepResult] = []
    exit_code = 0

    def record(name: str, command: list[str], code: int, detail: str = "") -> None:
        nonlocal exit_code
        status = "pass" if code == 0 else "fail"
        if status == "fail":
            exit_code = 1
        steps.append(
            StepResult(name=name, command=" ".join(command), exit_code=code, status=status, detail=detail[:500])
        )

    # L0 shape
    shape_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_pipeline_shape.py",
        "-k",
        "sync_skips_tier1 or execute_job_runs_tier1",
        "-v",
    ]
    code, out = _run(shape_cmd)
    record("shape_tests", shape_cmd, code, out.splitlines()[-1] if out else "")

    prereq_cmd = [sys.executable, "scripts/probe_tier1.py", "--prereqs"]
    code, out = _run(prereq_cmd)
    record("prereqs", prereq_cmd, code, out.splitlines()[-1] if out else "")

    filled, fill_detail = canary_filled()
    steps.append(
        StepResult(
            name="canary_file",
            command="(check docs/tier1_canary_set.json)",
            exit_code=0 if filled else 1,
            status="pass" if filled else "fail",
            detail=fill_detail,
        )
    )
    if not filled:
        exit_code = 1

    if args.skip_live:
        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "mode": "skip-live",
            "steps": [asdict(s) for s in steps],
            "exit_code": exit_code,
        }
        RESULTS.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if args.json:
            print(json.dumps(report, indent=2))
        return exit_code

    connect_cmd = [sys.executable, "scripts/probe_tier1.py", "--connect-test"]
    code, out = _run(connect_cmd)
    record("mlx_connect", connect_cmd, code, out.splitlines()[-1] if out else "")

    if filled:
        iso_args = [sys.executable, "scripts/probe_tier1_canary.py", "--file", str(CANARY), "--json"]
        if args.limit:
            iso_args.extend(["--limit", str(args.limit)])
        code, out = _run(iso_args)
        record("isolation_canary", iso_args, code, out.splitlines()[-1] if out else "")

        api_args = [sys.executable, "scripts/e2e_tier1_canary.py", "--file", str(CANARY), "--json"]
        if args.limit:
            api_args.extend(["--limit", str(args.limit)])
        code, out = _run(api_args)
        record("api_canary", api_args, code, out.splitlines()[-1] if out else "")

        score_cmd = [sys.executable, "scripts/run_canary_score.py", "--tier", "tier1", "--json"]
        code, out = _run(score_cmd)
        detail = "tier1 SKIP" if "SKIP" in out else out.splitlines()[-1] if out else ""
        record("canary_score", score_cmd, code, detail)

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "live",
        "steps": [asdict(s) for s in steps],
        "exit_code": exit_code,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report: {REPORT}")
    if args.json:
        print(json.dumps(report, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
