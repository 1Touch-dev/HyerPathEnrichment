"""Full-path E2E runner (Windows-friendly; avoids CRLF issues in .sh wrappers).

Chains existing backend/scripts e2e scripts and writes an aggregate report.

Modes:
  --ci   (default)  e2e_compose_test.sh → e2e_fake_sidecars.sh
  --live            probe_sidecars.sh → e2e_tier2.sh → e2e_tier3.sh → e2e_realworld_strict.sh
  --all             --ci then --live

Env:
  E2E_SKIP_COMPOSE=1   skip e2e_compose_test.sh when stack already up
  E2E_KEEP_STACK=1     forwarded to child scripts that honor it

Report: backend/.e2e-results/full-path-report.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
RESULTS = ROOT / ".e2e-results"
REPORT_PATH = RESULTS / "full-path-report.json"

CHILD_REPORTS: dict[str, str] = {
    "fake_sidecars": "fake-sidecars-report.json",
    "tier2": "tier2-report.json",
    "tier3": "tier3-report.json",
    "realworld_strict": "strict-report.json",
}

STAGES: dict[str, list[tuple[str, str]]] = {
    "ci": [
        ("compose_test", "e2e_compose_test.sh"),
        ("fake_sidecars", "e2e_fake_sidecars.sh"),
    ],
    "live": [
        ("probe_sidecars", "probe_sidecars.sh"),
        ("tier2", "e2e_tier2.sh"),
        ("tier3", "e2e_tier3.sh"),
        ("realworld_strict", "e2e_realworld_strict.sh"),
    ],
    "all": [
        ("compose_test", "e2e_compose_test.sh"),
        ("fake_sidecars", "e2e_fake_sidecars.sh"),
        ("probe_sidecars", "probe_sidecars.sh"),
        ("tier2", "e2e_tier2.sh"),
        ("tier3", "e2e_tier3.sh"),
        ("realworld_strict", "e2e_realworld_strict.sh"),
    ],
}


@dataclass
class StageResult:
    name: str
    script: str
    ok: bool
    exit_code: int
    duration_seconds: float
    skipped: bool
    skip_reason: str | None
    child_report: str | None


def resolve_bash() -> list[str]:
    """Return argv prefix to run bash scripts (native bash or WSL on Windows)."""
    if platform.system() == "Windows":
        wsl = shutil.which("wsl")
        if wsl:
            return [wsl, "bash"]
    bash = shutil.which("bash")
    if bash:
        return [bash]
    return []


def docker_available() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    try:
        subprocess.run(
            [docker, "info"],
            capture_output=True,
            check=True,
            timeout=30,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


def _bash_script_path(bash_prefix: list[str], script: Path) -> str:
    resolved = script.resolve()
    if bash_prefix and Path(bash_prefix[0]).name.lower().startswith("wsl"):
        drive = resolved.drive.rstrip(":").lower()
        rest = resolved.as_posix().split(":", 1)[-1]
        return f"/mnt/{drive}{rest}"
    return resolved.as_posix()


def run_script(bash_prefix: list[str], script_name: str) -> int:
    script = SCRIPTS / script_name
    if not script.is_file():
        raise FileNotFoundError(f"Missing script: {script}")
    script_path = _bash_script_path(bash_prefix, script)
    cmd = [*bash_prefix, script_path]
    print("+", " ".join(cmd), flush=True)
    completed = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return int(completed.returncode)


def run_stage(
    bash_prefix: list[str],
    name: str,
    script_name: str,
) -> StageResult:
    skip_reason: str | None = None
    if name == "compose_test" and os.environ.get("E2E_SKIP_COMPOSE", "0") == "1":
        print(f"SKIP  {name} (E2E_SKIP_COMPOSE=1)", flush=True)
        return StageResult(
            name=name,
            script=script_name,
            ok=True,
            exit_code=0,
            duration_seconds=0.0,
            skipped=True,
            skip_reason="E2E_SKIP_COMPOSE=1",
            child_report=CHILD_REPORTS.get(name),
        )

    print(f"\n========== stage: {name} ({script_name}) ==========", flush=True)
    start = time.monotonic()
    exit_code = run_script(bash_prefix, script_name)
    duration = time.monotonic() - start

    if exit_code == 0:
        print(f"PASS  {name} (exit={exit_code}, {duration:.1f}s)", flush=True)
    else:
        print(f"FAIL  {name} (exit={exit_code}, {duration:.1f}s)", flush=True)

    return StageResult(
        name=name,
        script=script_name,
        ok=exit_code == 0,
        exit_code=exit_code,
        duration_seconds=round(duration, 2),
        skipped=False,
        skip_reason=None,
        child_report=CHILD_REPORTS.get(name),
    )


def write_report(mode: str, stages: list[StageResult]) -> dict:
    passed = sum(1 for s in stages if s.ok)
    failed = sum(1 for s in stages if not s.ok and not s.skipped)
    skipped = sum(1 for s in stages if s.skipped)
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": mode,
        "stages": [
            {
                "name": s.name,
                "script": s.script,
                "ok": s.ok,
                "exit_code": s.exit_code,
                "duration_seconds": s.duration_seconds,
                "skipped": s.skipped,
                "skip_reason": s.skip_reason,
                "child_report": s.child_report,
            }
            for s in stages
        ],
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nFull-path report: {REPORT_PATH}", flush=True)
    print(
        f"Summary: {report['passed']} passed, {report['failed']} failed, {report['skipped']} skipped",
        flush=True,
    )
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full-path backend E2E stages.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ci", action="store_true", help="CI-safe compose + fake sidecars (default)")
    group.add_argument("--live", action="store_true", help="Live sidecar + tier probes")
    group.add_argument("--all", action="store_true", help="Run CI then live stages")
    return parser.parse_args(argv)


def resolve_mode(args: argparse.Namespace) -> str:
    if args.live:
        return "live"
    if args.all:
        return "all"
    return "ci"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = resolve_mode(args)

    bash_prefix = resolve_bash()
    if not bash_prefix:
        print(
            "ERROR: bash not found. Install Git Bash/WSL or run from Linux.",
            file=sys.stderr,
        )
        return 127

    if not docker_available():
        print(
            "WARN: Docker unavailable — stages will likely fail. "
            "Install/start Docker Desktop (WSL2 backend on Windows).",
            file=sys.stderr,
        )

    stages: list[StageResult] = []
    for name, script_name in STAGES[mode]:
        result = run_stage(bash_prefix, name, script_name)
        stages.append(result)

    report = write_report(mode, stages)
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
