"""Run Tier 2–4 enrichers in isolation and report OK / EMPTY / SKIP.

Unlike pytest shape tests (mocked) or e2e_realworld_strict (pass/fail gates),
this script shows each enricher's raw fragment so you can see which tools are
missing, misconfigured, or returning no data.

Usage:
  cd backend
  python scripts/probe_enrichers.py              # run all probes
  python scripts/probe_enrichers.py --prereqs    # audit CLIs / env only
  python scripts/probe_enrichers.py --only sherlock,email_verify
  python scripts/probe_enrichers.py --json       # machine-readable summary

Load `.env` from backend/ automatically via get_settings().
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.enrichers import (
    CrossLinkedEnricher,
    EmailDiscoverEnricher,
    EmailVerifyEnricher,
    GitReconEnricher,
    JobSpyEnricher,
    LocalBusinessEnricher,
    MaigretEnricher,
    SherlockEnricher,
    SocialAnalyzerEnricher,
    TheHarvesterEnricher,
)
from app.enrichers.base import Enricher
from app.models import EnrichmentRequest

RESULTS_DIR = ROOT / ".e2e-results"


@dataclass
class PrereqRow:
    name: str
    tier: str
    present: bool
    detail: str


@dataclass
class ProbeRow:
    name: str
    tier: str
    status: str  # SKIP | OK | EMPTY | CRASH
    keys: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    fragment: dict[str, Any] = field(default_factory=dict)
    note: str = ""


# JobSpy pulls numpy/pandas; native Windows Python 3.13 + MINGW numpy can segfault.
JOBSPY_SUBPROCESS_TIMEOUT = 180.0
WINDOWS_JOBSPY_NOTE = (
    "skipped on native Windows (python-jobspy/numpy may segfault) - "
    "test in Docker/WSL or pass --include-jobspy"
)


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


def audit_prerequisites() -> list[PrereqRow]:
    settings = get_settings()
    rows: list[PrereqRow] = []

    def cli(name: str, tier: str, binary: str) -> None:
        path = shutil.which(binary)
        rows.append(
            PrereqRow(
                name=name,
                tier=tier,
                present=path is not None,
                detail=path or f"`{binary}` not on PATH",
            )
        )

    cli("Sherlock", "2", "sherlock")
    cli("Maigret", "2", "maigret")
    cli("TheHarvester", "3", "theHarvester")
    cli("CrossLinked", "3", "crosslinked")
    cli("Email Discover", "3", settings.email_sleuth_bin)

    gitrecon = settings.gitrecon_script.strip()
    rows.append(
        PrereqRow(
            name="GitRecon",
            tier="3",
            present=bool(gitrecon and Path(gitrecon).is_file()),
            detail=gitrecon if gitrecon else "GITRECON_SCRIPT unset",
        )
    )

    jobspy_ok = importlib.util.find_spec("jobspy") is not None
    if jobspy_ok and sys.platform == "win32":
        jobspy_detail = "package installed (runtime probe skipped on native Windows unless --include-jobspy)"
    elif jobspy_ok:
        jobspy_detail = "import jobspy OK"
    else:
        jobspy_detail = "pip install .[enrichers]"
    rows.append(
        PrereqRow(
            name="JobSpy",
            tier="4",
            present=jobspy_ok,
            detail=jobspy_detail,
        )
    )

    dns_ok = importlib.util.find_spec("dns") is not None
    rows.append(
        PrereqRow(
            name="Email Verify (MX)",
            tier="3",
            present=dns_ok,
            detail="dnspython installed" if dns_ok else "pip install .[enrichers]",
        )
    )

    def url(name: str, tier: str, value: str, env: str) -> None:
        ok = bool(value.strip())
        rows.append(
            PrereqRow(
                name=name,
                tier=tier,
                present=ok,
                detail=value.strip() or f"{env} unset",
            )
        )

    url("Social Analyzer", "2", settings.social_analyzer_url, "SOCIAL_ANALYZER_URL")
    url("Email Verify (AfterShip)", "3", settings.email_verifier_url, "EMAIL_VERIFIER_URL")
    url("Local Business", "4", settings.gmaps_scraper_url, "GMAPS_SCRAPER_URL")
    url("Email Verify (SMTP)", "3", settings.reacher_url, "REACHER_URL")

    try:
        import MailChecker  # noqa: F401

        mailchecker_detail = "mailchecker OK"
        mailchecker_ok = True
    except ImportError:
        mailchecker_detail = "mailchecker missing from core deps"
        mailchecker_ok = False
    rows.append(
        PrereqRow(
            name="Email Verify (disposable blocklist)",
            tier="3",
            present=mailchecker_ok,
            detail=mailchecker_detail,
        )
    )

    return rows


def build_tests() -> list[tuple[str, str, Enricher, EnrichmentRequest]]:
    return [
        ("Sherlock", "2", SherlockEnricher(), EnrichmentRequest(username="torvalds")),
        ("Maigret", "2", MaigretEnricher(), EnrichmentRequest(username="torvalds")),
        (
            "Social Analyzer",
            "2",
            SocialAnalyzerEnricher(),
            EnrichmentRequest(username="torvalds"),
        ),
        ("GitRecon", "3", GitReconEnricher(), EnrichmentRequest(username="torvalds")),
        ("TheHarvester", "3", TheHarvesterEnricher(), EnrichmentRequest(company="Microsoft")),
        (
            "Email Discover",
            "3",
            EmailDiscoverEnricher(),
            EnrichmentRequest(username="torvalds", company="Microsoft"),
        ),
        (
            "Email Verify",
            "3",
            EmailVerifyEnricher(),
            EnrichmentRequest(email="noreply@github.com"),
        ),
        ("CrossLinked", "3", CrossLinkedEnricher(), EnrichmentRequest(company="Microsoft")),
        (
            "JobSpy",
            "4",
            JobSpyEnricher(),
            EnrichmentRequest(job_search="software engineer remote"),
        ),
        (
            "Local Business",
            "4",
            LocalBusinessEnricher(),
            EnrichmentRequest(business="coffee shop San Francisco"),
        ),
    ]


def _note_for_empty(name: str, settings: Any) -> str:
    notes = {
        "Sherlock": "install sherlock CLI on PATH",
        "Maigret": "install maigret CLI on PATH",
        "Social Analyzer": "start sidecar; set SOCIAL_ANALYZER_URL",
        "GitRecon": "clone gitrecon; set GITRECON_SCRIPT",
        "TheHarvester": "install theHarvester CLI on PATH",
        "Email Discover": "email-sleuth missing - fallback may still guess an email",
        "Email Verify": "set EMAIL_VERIFIER_URL for AfterShip; dnspython via .[enrichers]; REACHER_URL when EMAIL_VERIFY_LEVEL=smtp",
        "CrossLinked": "install crosslinked CLI on PATH",
        "JobSpy": "pip install .[enrichers] (python-jobspy)",
        "Local Business": "start gmaps sidecar; set GMAPS_SCRAPER_URL (slow: 1-5 min)",
    }
    if name == "Social Analyzer" and not settings.social_analyzer_url.strip():
        return "SOCIAL_ANALYZER_URL unset"
    if name == "Local Business" and not settings.gmaps_scraper_url.strip():
        return "GMAPS_SCRAPER_URL unset"
    return notes.get(name, "")


def _request_payload(request: EnrichmentRequest) -> dict[str, Any]:
    return request.model_dump(mode="json", exclude_none=True)


def _probe_jobspy_subprocess(request: EnrichmentRequest) -> tuple[str, dict[str, Any], str]:
    """Run JobSpy in a child process so a numpy segfault cannot kill the probe script."""
    payload = json.dumps(_request_payload(request))
    code = f"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path({str(ROOT)!r})
sys.path.insert(0, str(ROOT))

from app.enrichers.jobspy import JobSpyEnricher
from app.models import EnrichmentRequest

async def _run():
    req = EnrichmentRequest(**json.loads({payload!r}))
    return await JobSpyEnricher().run(req)

print(json.dumps(asyncio.run(_run())))
"""
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=JOBSPY_SUBPROCESS_TIMEOUT,
            cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired:
        return "CRASH", {}, f"JobSpy subprocess timed out after {JOBSPY_SUBPROCESS_TIMEOUT:.0f}s"

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip().splitlines()
        hint = stderr[-1] if stderr else f"exit code {completed.returncode}"
        if completed.returncode < 0:
            hint = f"process crashed ({hint}) - common on native Windows numpy builds"
        return "CRASH", {}, hint

    stdout = (completed.stdout or "").strip()
    if not stdout:
        return "EMPTY", {}, "JobSpy subprocess returned no output"

    try:
        fragment = json.loads(stdout)
    except json.JSONDecodeError:
        return "CRASH", {}, "JobSpy subprocess returned invalid JSON"

    if fragment:
        return "OK", fragment, ""
    return "EMPTY", {}, _note_for_empty("JobSpy", get_settings())


def _row_from_fragment(
    name: str,
    tier: str,
    status: str,
    fragment: dict[str, Any],
    note: str,
) -> ProbeRow:
    return ProbeRow(
        name=name,
        tier=tier,
        status=status,
        keys=sorted(k for k in fragment if k != "sources"),
        sources=list(fragment.get("sources") or []),
        fragment=fragment,
        note=note,
    )


async def probe_enrichers(
    only: set[str] | None = None,
    *,
    include_jobspy: bool = False,
    skip: set[str] | None = None,
) -> list[ProbeRow]:
    settings = get_settings()
    rows: list[ProbeRow] = []
    skip = skip or set()

    for name, tier, enricher, request in build_tests():
        slug = _slug(name)
        if only and slug not in only:
            continue
        if slug in skip:
            rows.append(
                ProbeRow(name=name, tier=tier, status="SKIP", note="excluded via --skip")
            )
            continue

        if slug == "jobspy" and sys.platform == "win32" and not include_jobspy:
            rows.append(
                ProbeRow(name=name, tier=tier, status="SKIP", note=WINDOWS_JOBSPY_NOTE)
            )
            continue

        if not await enricher.validate(request):
            rows.append(
                ProbeRow(
                    name=name,
                    tier=tier,
                    status="SKIP",
                    note="validate() returned False - missing required request field",
                )
            )
            continue

        if slug == "jobspy" and include_jobspy:
            status, fragment, note = _probe_jobspy_subprocess(request)
            rows.append(_row_from_fragment(name, tier, status, fragment, note))
            continue

        fragment = await enricher.run(request)
        status = "OK" if fragment else "EMPTY"
        rows.append(
            _row_from_fragment(
                name,
                tier,
                status,
                fragment,
                "" if fragment else _note_for_empty(name, settings),
            )
        )

    return rows


def print_prereqs(rows: list[PrereqRow]) -> None:
    print("== prerequisites audit ==")
    for row in rows:
        mark = "OK" if row.present else "MISS"
        print(f"{mark:4}  tier{row.tier}  {row.name}: {row.detail}")


def print_probes(rows: list[ProbeRow]) -> None:
    print("\n== enricher isolation probe ==")
    for row in rows:
        if row.status == "SKIP":
            print(f"SKIP  tier{row.tier}  {row.name}: {row.note}")
            continue
        if row.status == "OK":
            summary = ", ".join(row.keys) or "(no data keys)"
            print(f"OK    tier{row.tier}  {row.name}: keys=[{summary}] sources={row.sources}")
            continue
        if row.status == "CRASH":
            hint = f" - {row.note}" if row.note else ""
            print(f"CRASH tier{row.tier}  {row.name}:{hint}")
            continue
        hint = f" - {row.note}" if row.note else ""
        print(f"EMPTY tier{row.tier}  {row.name}: {{}}{hint}")


def print_scorecard(rows: list[ProbeRow]) -> None:
    print("\n== scorecard ==")
    print(f"{'Source':<18} {'Tier':<5} {'Status':<6} {'Data keys'}")
    print("-" * 60)
    for row in rows:
        keys = ", ".join(row.keys) if row.keys else "-"
        print(f"{row.name:<18} {row.tier:<5} {row.status:<6} {keys}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Tier 2–4 enrichers in isolation")
    parser.add_argument(
        "--prereqs",
        action="store_true",
        help="Audit CLIs, imports, and env vars only (no enricher runs)",
    )
    parser.add_argument(
        "--only",
        metavar="NAMES",
        help="Comma-separated enricher slugs (e.g. sherlock,email_verify,local_business)",
    )
    parser.add_argument(
        "--skip",
        metavar="NAMES",
        help="Comma-separated enricher slugs to skip",
    )
    parser.add_argument(
        "--include-jobspy",
        action="store_true",
        help="Run JobSpy on native Windows in a subprocess (may still crash on bad numpy builds)",
    )
    parser.add_argument("--json", action="store_true", help="Write JSON report to .e2e-results/")
    args = parser.parse_args()

    only = {_slug(part.strip()) for part in args.only.split(",") if part.strip()} if args.only else None
    skip = {_slug(part.strip()) for part in args.skip.split(",") if part.strip()} if args.skip else None

    prereqs = audit_prerequisites()
    print_prereqs(prereqs)

    if args.prereqs:
        return 0

    if sys.platform == "win32" and not args.include_jobspy and (only is None or "jobspy" in (only or set())):
        print("\nNote: JobSpy auto-skipped on native Windows (use --include-jobspy or Docker/WSL).")

    probes = await probe_enrichers(only=only, include_jobspy=args.include_jobspy, skip=skip)
    print_probes(probes)
    print_scorecard(probes)

    if args.json:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "prerequisites": [asdict(r) for r in prereqs],
            "probes": [
                {
                    **asdict(r),
                    "fragment": r.fragment if r.status == "OK" else {},
                }
                for r in probes
            ],
            "summary": {
                "ok": sum(1 for r in probes if r.status == "OK"),
                "empty": sum(1 for r in probes if r.status == "EMPTY"),
                "skip": sum(1 for r in probes if r.status == "SKIP"),
                "crash": sum(1 for r in probes if r.status == "CRASH"),
            },
        }
        path = RESULTS_DIR / "probe-enrichers.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nReport written to {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
