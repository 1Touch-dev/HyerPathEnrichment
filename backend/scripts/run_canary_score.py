"""Ops runner for the 20-profile canary run/score workflow.

Copies example canary JSON to local gitignored paths when missing, runs Tier 2–4
isolation probes (and Tier 1 when Multilogin prerequisites are present), and writes
a combined summary under ``backend/.e2e-results/``.

Usage:
  cd backend
  python scripts/run_canary_score.py --help
  python scripts/run_canary_score.py --dry-run
  python scripts/run_canary_score.py --tier tier234 --json
  python scripts/run_canary_score.py --tier all --limit 3

Tier 1 requires local Multilogin + ``docs/tier1_canary_set.json`` filled with real
public profile URLs (never commit that file). When MLX is unavailable the runner
records Tier 1 as SKIP instead of failing the whole run.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
RESULTS_DIR = ROOT / ".e2e-results"

TIER1_EXAMPLE = DOCS / "tier1_canary_set.example.json"
TIER1_LOCAL = DOCS / "tier1_canary_set.json"
TIER234_EXAMPLE = DOCS / "tier234_canary_set.example.json"
TIER234_LOCAL = DOCS / "tier234_canary_set.json"

TIER234_REPORT = RESULTS_DIR / "tier234-canary.json"
TIER1_PROBE_REPORT = RESULTS_DIR / "probe-tier1-canary.json"
COMBINED_REPORT = RESULTS_DIR / "canary-run-score.json"


def _load_module(name: str, path: Path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def ensure_canary_file(example: Path, local: Path, *, dry_run: bool) -> str:
    """Copy example → local when local is missing. Returns action label."""
    if local.is_file():
        return "use_existing"
    if not example.is_file():
        raise FileNotFoundError(f"example canary missing: {example}")
    if dry_run:
        return "would_copy"
    shutil.copy2(example, local)
    return "copied"


def tier1_prereqs_ready() -> tuple[bool, list[dict[str, Any]]]:
    probe_tier1 = _load_module("probe_tier1_runner", ROOT / "scripts" / "probe_tier1.py")
    rows = probe_tier1.audit_prerequisites()
    required = {
        "ENABLE_TIER1",
        "MULTILOGIN_EMAIL",
        "MULTILOGIN_PASSWORD",
        "MULTILOGIN_FOLDER_ID",
        "LINKEDIN_BOT_EMAIL",
        "LINKEDIN_BOT_PASSWORD",
        "selenium",
    }
    serialized = [asdict(row) for row in rows]
    ready = all(row["present"] for row in serialized if row["name"] in required)
    return ready, serialized


def tier1_local_filled(local: Path) -> bool:
    if not local.is_file():
        return False
    try:
        entries = json.loads(local.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(entries, list) or not entries:
        return False
    for entry in entries:
        url = str(entry.get("linkedin_url") or "")
        if "your-" in url or "example-" in url:
            return False
    return True


def run_python_script(script: Path, args: list[str], *, dry_run: bool) -> dict[str, Any]:
    cmd = [sys.executable, str(script), *args]
    label = " ".join(cmd)
    if dry_run:
        return {"status": "DRY_RUN", "command": label, "exit_code": None}
    print(f"+ {label}", flush=True)
    completed = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return {
        "status": "RAN",
        "command": label,
        "exit_code": completed.returncode,
    }


def load_json_report(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def summarize_tier234(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {"status": "MISSING", "summary": {}}
    summary = report.get("summary") or {}
    fail = int(summary.get("cells_fail") or summary.get("profiles_fail") or 0)
    return {
        "status": "PASS" if fail == 0 else "FAIL",
        "summary": summary,
        "report_path": str(TIER234_REPORT),
    }


def summarize_tier1(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {"status": "MISSING", "summary": {}}
    summary = report.get("summary") or {}
    fail = int(summary.get("fail") or 0)
    return {
        "status": "PASS" if fail == 0 else "FAIL",
        "summary": summary,
        "report_path": str(TIER1_PROBE_REPORT),
    }


def write_combined_report(payload: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    COMBINED_REPORT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nCombined report: {COMBINED_REPORT}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run 20-profile canary probes and write a combined score summary",
    )
    parser.add_argument(
        "--tier",
        choices=["tier234", "tier1", "all"],
        default="all",
        help="Which canary set to run (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only run the first N profiles per tier",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned commands and file copies without running probes",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Pass --json to underlying probe scripts and write combined summary",
    )
    parser.add_argument(
        "--include-jobspy",
        action="store_true",
        help="Pass --include-jobspy to probe_enrichers (native Windows JobSpy)",
    )
    parser.add_argument(
        "--skip-tier1",
        action="store_true",
        help="Force Tier 1 SKIP even when Multilogin prerequisites are present",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    actions: dict[str, Any] = {
        "tier234": {},
        "tier1": {},
    }
    exit_code = 0

    if args.tier in {"tier234", "all"}:
        copy_action = ensure_canary_file(TIER234_EXAMPLE, TIER234_LOCAL, dry_run=args.dry_run)
        actions["tier234"]["canary_file"] = {
            "example": str(TIER234_EXAMPLE),
            "local": str(TIER234_LOCAL),
            "action": copy_action,
        }
        probe_args = ["--canary", str(TIER234_LOCAL)]
        if args.limit is not None:
            probe_args.extend(["--limit", str(args.limit)])
        if args.json:
            probe_args.append("--json")
        if args.include_jobspy:
            probe_args.append("--include-jobspy")
        run_result = run_python_script(
            ROOT / "scripts" / "probe_enrichers.py",
            probe_args,
            dry_run=args.dry_run,
        )
        actions["tier234"]["probe"] = run_result
        if not args.dry_run and run_result.get("exit_code") not in {0, None}:
            exit_code = 1

    if args.tier in {"tier1", "all"}:
        copy_action = ensure_canary_file(TIER1_EXAMPLE, TIER1_LOCAL, dry_run=args.dry_run)
        actions["tier1"]["canary_file"] = {
            "example": str(TIER1_EXAMPLE),
            "local": str(TIER1_LOCAL),
            "action": copy_action,
        }

        if args.skip_tier1:
            actions["tier1"]["status"] = "SKIP"
            actions["tier1"]["reason"] = "--skip-tier1"
        elif args.dry_run:
            ready, prereqs = tier1_prereqs_ready()
            filled = tier1_local_filled(TIER1_LOCAL)
            actions["tier1"]["status"] = "DRY_RUN"
            actions["tier1"]["prereqs_ready"] = ready
            actions["tier1"]["local_filled"] = filled
            actions["tier1"]["prereqs"] = prereqs
            json_args = ["--json"] if args.json else []
            actions["tier1"]["planned_probe"] = (
                f"{sys.executable} scripts/probe_tier1_canary.py "
                f"--file {TIER1_LOCAL} {' '.join(json_args)}".strip()
            )
        else:
            ready, prereqs = tier1_prereqs_ready()
            actions["tier1"]["prereqs"] = prereqs
            if not ready:
                actions["tier1"]["status"] = "SKIP"
                actions["tier1"]["reason"] = (
                    "Multilogin prerequisites missing (see probe_tier1.py --prereqs)"
                )
            elif not tier1_local_filled(TIER1_LOCAL):
                actions["tier1"]["status"] = "SKIP"
                actions["tier1"]["reason"] = (
                    "tier1_canary_set.json still has placeholder URLs — replace with real public profiles"
                )
            else:
                probe_args = ["--file", str(TIER1_LOCAL)]
                if args.json:
                    probe_args.append("--json")
                run_result = run_python_script(
                    ROOT / "scripts" / "probe_tier1_canary.py",
                    probe_args,
                    dry_run=False,
                )
                actions["tier1"]["probe"] = run_result
                actions["tier1"]["status"] = "RAN"
                if run_result.get("exit_code") not in {0, None}:
                    exit_code = 1

    tier234_report = None if args.dry_run else load_json_report(TIER234_REPORT)
    tier1_report = None if args.dry_run else load_json_report(TIER1_PROBE_REPORT)
    combined = {
        "generated_at": started,
        "dry_run": args.dry_run,
        "tier": args.tier,
        "limit": args.limit,
        "actions": actions,
        "results": {
            "tier234": summarize_tier234(tier234_report),
            "tier1": summarize_tier1(tier1_report)
            if actions.get("tier1", {}).get("status") == "RAN"
            else {
                "status": actions.get("tier1", {}).get("status", "NOT_RUN"),
                "reason": actions.get("tier1", {}).get("reason"),
            },
        },
    }
    if args.dry_run:
        print(json.dumps(combined, indent=2))
    elif args.json:
        write_combined_report(combined)

    if args.dry_run:
        print("\nDry run complete — no probes executed.")
        return 0

    print("\n== canary run/score summary ==")
    if "tier234" in actions:
        tier234_result = load_json_report(TIER234_REPORT)
        summary = summarize_tier234(tier234_result)
        print(f"Tier 2–4: {summary['status']}")
    if "tier1" in actions:
        tier1_status = actions["tier1"].get("status", "NOT_RUN")
        print(f"Tier 1:   {tier1_status}")
        if actions["tier1"].get("reason"):
            print(f"          {actions['tier1']['reason']}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
