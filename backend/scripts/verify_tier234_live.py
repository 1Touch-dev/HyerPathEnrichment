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
    venv = ROOT / ".venv" / "bin" / "python"
    if venv.is_file():
        return str(venv)
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
            wsl_path = "/mnt/" + str(ROOT.drive).rstrip(":").lower() + str(ROOT)[2:].replace("\\", "/")
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
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def _load_json(name: str) -> dict | None:
    path = RESULTS / name
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


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
            StepResult(name=name, command=" ".join(command), exit_code=code, status=status, detail=detail[:500])
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
    record("unit_tests", unit_cmd, code, out.splitlines()[-1] if out else "")

    if args.skip_live:
        report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "mode": "skip-live", "steps": [asdict(s) for s in steps], "exit_code": exit_code}
        RESULTS.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return exit_code

    live_steps: list[tuple[str, list[str]]] = [
        ("probe_sidecars", _bash("probe_sidecars.sh")),
        ("tier2_e2e", _bash("e2e_tier2.sh")),
        ("tier3_e2e", _bash("e2e_tier3.sh")),
        ("strict_e2e", _bash("e2e_realworld_strict.sh")),
        ("full_path_live", _bash("e2e_full_path.sh", "--live")),
    ]
    for name, cmd in live_steps:
        code, out = _run(cmd)
        record(name, cmd, code, out.splitlines()[-1] if out else "")

    score_cmd = [_python(), "scripts/run_canary_score.py", "--tier", "tier234", "--json"]
    code, out = _run(score_cmd)
    record("canary_score", score_cmd, code, out.splitlines()[-1] if out else "")

    strict = _load_json("strict-report.json")
    if strict and strict.get("failed", 1) != 0:
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
                detail="failed=0" if strict else "report missing",
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
