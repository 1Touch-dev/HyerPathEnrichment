"""Tier 1 live proof runner (Task 13 / M3) — Windows-native path.

Runs layered verification and writes backend/.e2e-results/verify-tier1-live.json.

Usage:
  cd backend
  python scripts/verify_tier1_live.py --skip-live
  python scripts/verify_tier1_live.py --json
  python scripts/verify_tier1_live.py --limit 3
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
DOCS = ROOT / "docs"
RESULTS = ROOT / ".e2e-results"
REPORT = RESULTS / "verify-tier1-live.json"
CANARY = DOCS / "tier1_canary_set.json"


@dataclass
class StepResult:
    name: str
    command: str
    exit_code: int
    status: str
    detail: str = ""


def _run(cmd: list[str], *, cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def _canary_filled() -> bool:
    if not CANARY.is_file():
        return False
    try:
        entries = json.loads(CANARY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(entries, list) or not entries:
        return False
    for entry in entries:
        url = str(entry.get("linkedin_url") or "")
        if "your-" in url or "example-" in url:
            return False
    return True


def _load_json(name: str) -> dict | None:
    path = RESULTS / name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Tier 1 live proof matrix")
    parser.add_argument("--skip-live", action="store_true", help="Shape + prereqs only")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Canary profile limit")
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

    shape_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_pipeline_shape.py::test_sync_skips_tier1_photo",
        "tests/test_pipeline_shape.py::test_execute_job_runs_tier1_on_worker_path",
        "-q",
        "--tb=no",
    ]
    code, out = _run(shape_cmd)
    record("shape_tests", shape_cmd, code, out.splitlines()[-1] if out else "")

    prereq_cmd = [sys.executable, str(SCRIPTS / "probe_tier1.py"), "--prereqs"]
    code, out = _run(prereq_cmd)
    record("prereqs", prereq_cmd, code, "audit complete" if code == 0 else out[-200:])

    if args.skip_live:
        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "mode": "skip-live",
            "canary_filled": _canary_filled(),
            "steps": [asdict(s) for s in steps],
            "exit_code": exit_code,
        }
        RESULTS.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if args.json:
            print(json.dumps(report, indent=2))
        return exit_code

    if not _canary_filled():
        record("canary_file", ["check", str(CANARY)], 1, "tier1_canary_set.json missing or has placeholders")
    else:
        steps.append(
            StepResult(name="canary_file", command=f"check {CANARY}", exit_code=0, status="pass", detail="filled")
        )

    connect_cmd = [sys.executable, str(SCRIPTS / "probe_tier1.py"), "--connect-test"]
    code, out = _run(connect_cmd)
    record("mlx_connect", connect_cmd, code, out.splitlines()[-1] if out else "")

    canary_url = ""
    if _canary_filled():
        entries = json.loads(CANARY.read_text(encoding="utf-8"))
        for entry in entries:
            if entry.get("category") == "technical" and entry.get("expect_photo", True):
                canary_url = str(entry.get("linkedin_url") or "")
                break
        if not canary_url and entries:
            canary_url = str(entries[0].get("linkedin_url") or "")

    if canary_url:
        scrape_cmd = [
            sys.executable,
            str(SCRIPTS / "probe_tier1.py"),
            "--scrape",
            "--linkedin-url",
            canary_url,
        ]
        code, out = _run(scrape_cmd)
        record("isolation_scrape", scrape_cmd, code, out.splitlines()[-1] if out else "")

    probe_args = [sys.executable, str(SCRIPTS / "probe_tier1_canary.py"), "--file", str(CANARY), "--pool-status", "--json"]
    code, out = _run(probe_args)
    record("probe_canary", probe_args, code, out.splitlines()[-1] if out else "")

    probe_report = _load_json("probe-tier1-canary.json")
    if probe_report:
        fail = int((probe_report.get("summary") or {}).get("fail") or 0)
        if fail != 0:
            exit_code = 1
            steps.append(
                StepResult(
                    name="probe_canary_gate",
                    command="probe-tier1-canary.json fail==0",
                    exit_code=1,
                    status="fail",
                    detail=f"fail={fail}",
                )
            )
        else:
            steps.append(
                StepResult(
                    name="probe_canary_gate",
                    command="probe-tier1-canary.json fail==0",
                    exit_code=0,
                    status="pass",
                    detail="fail=0",
                )
            )

    e2e_args = [sys.executable, str(SCRIPTS / "e2e_tier1_canary.py"), "--file", str(CANARY), "--json"]
    if args.limit is not None:
        e2e_args.extend(["--limit", str(args.limit)])
    code, out = _run(e2e_args)
    record("api_canary", e2e_args, code, out.splitlines()[-1] if out else "")

    e2e_report = _load_json("tier1-canary.json")
    if e2e_report:
        summary = e2e_report.get("summary") or {}
        fail = int(summary.get("profiles_fail") or summary.get("fail") or 0)
        if fail != 0:
            exit_code = 1
            steps.append(
                StepResult(
                    name="api_canary_gate",
                    command="tier1-canary.json profiles_fail==0",
                    exit_code=1,
                    status="fail",
                    detail=f"profiles_fail={fail}",
                )
            )
        else:
            steps.append(
                StepResult(
                    name="api_canary_gate",
                    command="tier1-canary.json profiles_fail==0",
                    exit_code=0,
                    status="pass",
                    detail="profiles_fail=0",
                )
            )

    score_cmd = [sys.executable, str(SCRIPTS / "run_canary_score.py"), "--tier", "tier1", "--json"]
    if args.limit is not None:
        score_cmd.extend(["--limit", str(args.limit)])
    code, out = _run(score_cmd)
    record("canary_score", score_cmd, code, out.splitlines()[-1] if out else "")

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "live",
        "canary_filled": _canary_filled(),
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
