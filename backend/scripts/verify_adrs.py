#!/usr/bin/env python3
"""Verify formal ADR structure, content, and doc cross-links (Task 6).

Usage:
  python backend/scripts/verify_adrs.py
  python backend/scripts/verify_adrs.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
ADR_DIR = REPO_ROOT / "docs" / "adr"
RESULTS_DIR = BACKEND_ROOT / ".e2e-results"
REPORT_PATH = RESULTS_DIR / "verify-adrs.json"

ADR_FILENAME_RE = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")
DATE_RE = re.compile(r"\*\*Date:\*\*\s+\d{4}-\d{2}-\d{2}")
STATUS_ACCEPTED_RE = re.compile(r"\*\*Status:\*\*\s+Accepted\b")
DECISION_ALT_RE = re.compile(r"\bover\b|\binstead of\b", re.IGNORECASE)
TRADEOFFS_BULLET_RE = re.compile(r"^## Tradeoffs\s*\n(?:.*\n)*?^- ", re.MULTILINE)

TEMPLATE_HEADINGS = ("Status", "Date", "Context", "Decision", "Tradeoffs", "Consequences")
REQUIRED_ADR_NUMBERS = tuple(range(1, 7))
MIN_ACCEPTED = 6
CROSS_LINK_FILES = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "RULE.md",
    BACKEND_ROOT / "docs" / "ARCHITECTURE.md",
)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def _adr_files() -> list[Path]:
    return sorted(
        p
        for p in ADR_DIR.glob("0*.md")
        if p.name != "template.md" and ADR_FILENAME_RE.match(p.name)
    )


def _check_readme_index(readme: Path, adr_files: list[Path]) -> CheckResult:
    if not readme.is_file():
        return CheckResult("readme_exists", False, "docs/adr/README.md missing")
    text = readme.read_text(encoding="utf-8")
    missing: list[str] = []
    for path in adr_files:
        if path.name not in text:
            missing.append(path.name)
    if missing:
        return CheckResult(
            "readme_index",
            False,
            f"README missing table rows for: {', '.join(missing)}",
        )
    return CheckResult("readme_index", True, f"{len(adr_files)} ADRs indexed")


def _check_template() -> CheckResult:
    template = ADR_DIR / "template.md"
    if not template.is_file():
        return CheckResult("template_exists", False, "docs/adr/template.md missing")
    text = template.read_text(encoding="utf-8")
    missing = [h for h in TEMPLATE_HEADINGS if h not in text]
    if missing:
        return CheckResult(
            "template_headings",
            False,
            f"template missing headings: {', '.join(missing)}",
        )
    return CheckResult("template_headings", True, "all required headings present")


def _check_required_numbers(adr_files: list[Path]) -> CheckResult:
    found = {int(p.name[:4]) for p in adr_files}
    missing = [n for n in REQUIRED_ADR_NUMBERS if n not in found]
    bad_names = [p.name for p in adr_files if not ADR_FILENAME_RE.match(p.name)]
    if missing:
        return CheckResult(
            "required_numbers",
            False,
            f"missing ADRs: {', '.join(f'{n:04d}' for n in missing)}",
        )
    if bad_names:
        return CheckResult(
            "filename_pattern",
            False,
            f"invalid ADR filenames: {', '.join(bad_names)}",
        )
    return CheckResult("required_numbers", True, "0001-0006 present")


def _check_adr_content(path: Path) -> list[CheckResult]:
    text = path.read_text(encoding="utf-8")
    name = path.name
    results: list[CheckResult] = []

    if not STATUS_ACCEPTED_RE.search(text):
        results.append(CheckResult(f"{name}:status", False, "Status must be Accepted"))
    else:
        results.append(CheckResult(f"{name}:status", True))

    if not DATE_RE.search(text):
        results.append(CheckResult(f"{name}:date", False, "Date must be YYYY-MM-DD"))
    else:
        results.append(CheckResult(f"{name}:date", True))

    decision_match = re.search(r"^## Decision\s*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not decision_match or not DECISION_ALT_RE.search(decision_match.group(1)):
        results.append(
            CheckResult(
                f"{name}:decision",
                False,
                "Decision must mention chosen option over/in instead of alternative",
            )
        )
    else:
        results.append(CheckResult(f"{name}:decision", True))

    if not TRADEOFFS_BULLET_RE.search(text):
        results.append(
            CheckResult(f"{name}:tradeoffs", False, "Tradeoffs needs at least one bullet")
        )
    else:
        results.append(CheckResult(f"{name}:tradeoffs", True))

    return results


def _check_cross_links() -> CheckResult:
    missing: list[str] = []
    for path in CROSS_LINK_FILES:
        if not path.is_file():
            missing.append(str(path.relative_to(REPO_ROOT)))
            continue
        if "docs/adr" not in path.read_text(encoding="utf-8"):
            missing.append(str(path.relative_to(REPO_ROOT)))
    if missing:
        return CheckResult(
            "cross_links",
            False,
            f"files missing docs/adr reference: {', '.join(missing)}",
        )
    return CheckResult("cross_links", True, f"{len(CROSS_LINK_FILES)} files linked")


def _check_min_accepted(adr_files: list[Path]) -> CheckResult:
    accepted = 0
    for path in adr_files:
        if STATUS_ACCEPTED_RE.search(path.read_text(encoding="utf-8")):
            accepted += 1
    if accepted < MIN_ACCEPTED:
        return CheckResult(
            "min_accepted",
            False,
            f"need >= {MIN_ACCEPTED} Accepted ADRs, found {accepted}",
        )
    return CheckResult("min_accepted", True, f"{accepted} accepted")


def run_checks() -> tuple[list[CheckResult], bool]:
    adr_files = _adr_files()
    readme = ADR_DIR / "README.md"

    checks: list[CheckResult] = [
        _check_readme_index(readme, adr_files),
        _check_template(),
        _check_required_numbers(adr_files),
        _check_cross_links(),
        _check_min_accepted(adr_files),
    ]
    for path in adr_files:
        checks.extend(_check_adr_content(path))

    ok = all(c.passed for c in checks)
    return checks, ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify formal ADR structure")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write report to backend/.e2e-results/verify-adrs.json",
    )
    args = parser.parse_args()

    checks, ok = run_checks()
    accepted = sum(1 for c in checks if c.name.endswith(":status") and c.passed)

    report = {
        "task": "formal-adrs-06",
        "passed": ok,
        "accepted_count": accepted,
        "checks": [asdict(c) for c in checks],
    }

    if args.json:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if ok:
        print(f"adr verify ok ({accepted} accepted)")
        raise SystemExit(0)

    print("adr verify FAILED:", file=sys.stderr)
    for check in checks:
        if not check.passed:
            print(f"  - {check.name}: {check.detail}", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
