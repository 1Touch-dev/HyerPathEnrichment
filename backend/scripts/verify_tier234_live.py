"""Tier 2–4 live proof runner (M4–M10).

Chains live E2E scripts and writes backend/.e2e-results/verify-tier234-live.json.

Usage:
  cd backend
  python scripts/verify_tier234_live.py
  python scripts/verify_tier234_live.py --skip-live
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
RESULTS = ROOT / ".e2e-results"
REPORT = RESULTS / "verify-tier234-live.json"


def _python() -> str:
    for candidate in (
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


@dataclass
class StepResult:
    name: str
    command: str
    exit_code: int
    status: str
    detail: str = ""


def _bash(script: str, *extra: str) -> list[str]:
    """Prefer native bash; on Windows fall back to Git Bash if WSL is unavailable."""
    bash = shutil.which("bash")
    if bash:
        return [bash, str(SCRIPTS / script), *extra]
    if platform.system() == "Windows":
        for candidate in (
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ):
            if Path(candidate).is_file():
                return [candidate, str(SCRIPTS / script), *extra]
        wsl = shutil.which("wsl")
        if wsl:
            wsl_path = (
                "/mnt/" + str(ROOT.drive).rstrip(":").lower() + str(ROOT)[2:].replace("\\", "/")
            )
            wsl_script = f"{wsl_path}/scripts/{script}"
            return [wsl, "bash", wsl_script, *extra]
    return ["bash", str(SCRIPTS / script), *extra]


def _python_script(script: str, *extra: str) -> list[str]:
    return [_python(), str(SCRIPTS / script), *extra]


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def _load_json(name: str) -> dict | None:
    path = RESULTS / name
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _detail(out: str, *, max_lines: int = 8) -> str:
    lines = [ln for ln in (out or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    interesting = [
        ln
        for ln in lines
        if any(
            token in ln
            for token in (
                "FAIL",
                "Error",
                "error",
                "Traceback",
                "value_error",
                "ValidationError",
                "ModuleNotFoundError",
                "PASS  ",
            )
        )
    ]
    chosen = interesting[-max_lines:] if interesting else lines[-max_lines:]
    return " | ".join(chosen)[:500]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Tier 2–4 live proof matrix")
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    steps: list[StepResult] = []
    exit_code = 0

    def record(name: str, command: list[str], code: int, detail: str = "") -> None:
        nonlocal exit_code
        status = "pass" if code == 0 else "fail"
        if status == "fail":
            exit_code = 1
        steps.append(
            StepResult(
                name=name,
                command=" ".join(command),
                exit_code=code,
                status=status,
                detail=detail[:500],
            )
        )

    unit_cmd = [
        _python(),
        "-m",
        "pytest",
        "tests/test_pipeline_shape.py",
        "tests/test_tier2_merge.py",
        "tests/test_tier3_merge.py",
        "tests/test_enrichers.py",
        "-v",
        "--tb=no",
        "-q",
    ]
    code, out = _run(unit_cmd)
    record("unit_tests", unit_cmd, code, _detail(out) or (out.splitlines()[-1] if out else ""))

    if args.skip_live:
        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "mode": "skip-live",
            "steps": [asdict(s) for s in steps],
            "exit_code": exit_code,
        }
        RESULTS.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return exit_code

    # Do not re-run e2e_full_path.sh --live here: it duplicates tier2/tier3/strict
    # and exhausts GitHub API budget (gitrecon) after those steps already passed.
    live_steps: list[tuple[str, list[str]]] = [
        ("probe_sidecars", _bash("probe_sidecars.sh")),
        ("tier2_e2e", _bash("e2e_tier2.sh")),
        ("tier3_e2e", _bash("e2e_tier3.sh")),
        ("strict_e2e", _bash("e2e_realworld_strict.sh")),
        ("canary_score", _bash("e2e_canary_tier234.sh")),
    ]
    for name, cmd in live_steps:
        code, out = _run(cmd)
        record(name, cmd, code, _detail(out) or (out.splitlines()[-1] if out else ""))

    strict = _load_json("strict-report.json")
    if not strict:
        exit_code = 1
        steps.append(
            StepResult(
                name="strict_report_gate",
                command="strict-report.json failed==0",
                exit_code=1,
                status="fail",
                detail="report missing",
            )
        )
    elif strict.get("failed", 1) != 0:
        exit_code = 1
        steps.append(
            StepResult(
                name="strict_report_gate",
                command="strict-report.json failed==0",
                exit_code=1,
                status="fail",
                detail=f"failed={strict.get('failed')}",
            )
        )
    else:
        steps.append(
            StepResult(
                name="strict_report_gate",
                command="strict-report.json failed==0",
                exit_code=0,
                status="pass",
                detail="failed=0",
            )
        )

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
