"""Run Tier 2–4 enrichers in isolation and report OK / EMPTY / SKIP.

Unlike pytest shape tests (mocked) or e2e_realworld_strict (pass/fail gates),
this script shows each enricher's raw fragment so you can see which tools are
missing, misconfigured, or returning no data.

Usage:
  cd backend
  python scripts/probe_enrichers.py              # run all probes (default samples)
  python scripts/probe_enrichers.py --prereqs    # audit CLIs / env only
  python scripts/probe_enrichers.py --only sherlock,email_verify
  python scripts/probe_enrichers.py --json       # machine-readable summary
  python scripts/probe_enrichers.py --canary docs/tier234_canary_set.json --limit 3 --json

Load `.env` from backend/ automatically via get_settings().
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

_env_root = os.environ.get("E2E_BACKEND_ROOT")
ROOT = Path(_env_root) if _env_root else Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.config import get_settings
from app.enrichers.base import Enricher
from app.enrichers.crosslinked import CrossLinkedEnricher
from app.enrichers.email_discover import EmailDiscoverEnricher
from app.enrichers.email_verify import EmailVerifyEnricher
from app.enrichers.gitrecon import GitReconEnricher
from app.enrichers.jobspy import JobSpyEnricher
from app.enrichers.local_business import LocalBusinessEnricher
from app.enrichers.maigret import MaigretEnricher
from app.enrichers.sherlock import SherlockEnricher
from app.enrichers.social_analyzer import SocialAnalyzerEnricher
from app.enrichers.theharvester import TheHarvesterEnricher
from app.models import EnrichmentRequest

RESULTS_DIR = ROOT / ".e2e-results"

DEFAULT_PROFILE: dict[str, str] = {
    "username": "torvalds",
    "company": "Microsoft",
    "email": "noreply@github.com",
    "job_search": "software engineer remote",
    "business": "coffee shop San Francisco",
}

# slug -> (display name, tier, factory)
EnricherFactory = Callable[[], Enricher]
RequestBuilder = Callable[[dict[str, str]], EnrichmentRequest]

ENRICHER_SPECS: list[tuple[str, str, str, EnricherFactory, RequestBuilder]] = [
    (
        "sherlock",
        "Sherlock",
        "2",
        SherlockEnricher,
        lambda p: EnrichmentRequest(
            username=p.get("username") or None,
            requested_tiers=["tier2"],
        ),
    ),
    (
        "maigret",
        "Maigret",
        "2",
        MaigretEnricher,
        lambda p: EnrichmentRequest(
            username=p.get("username") or None,
            requested_tiers=["tier2"],
        ),
    ),
    (
        "social_analyzer",
        "Social Analyzer",
        "2",
        SocialAnalyzerEnricher,
        lambda p: EnrichmentRequest(
            username=p.get("username") or None,
            requested_tiers=["tier2"],
        ),
    ),
    (
        "gitrecon",
        "GitRecon",
        "3",
        GitReconEnricher,
        lambda p: EnrichmentRequest(
            username=p.get("username") or None,
            email=p.get("email") or None,
            requested_tiers=["tier3"],
        ),
    ),
    (
        "theharvester",
        "TheHarvester",
        "3",
        TheHarvesterEnricher,
        lambda p: EnrichmentRequest(
            company=p.get("company") or None,
            email=p.get("email") or None,
            requested_tiers=["tier3"],
        ),
    ),
    (
        "email_discover",
        "Email Discover",
        "3",
        EmailDiscoverEnricher,
        lambda p: EnrichmentRequest(
            username=p.get("username") or None,
            company=p.get("company") or None,
            requested_tiers=["tier3"],
        ),
    ),
    (
        "email_verify",
        "Email Verify",
        "3",
        EmailVerifyEnricher,
        lambda p: EnrichmentRequest(
            email=p.get("email") or None,
            username=p.get("username") or None,
            requested_tiers=["tier3"],
        ),
    ),
    (
        "crosslinked",
        "CrossLinked",
        "3",
        CrossLinkedEnricher,
        lambda p: EnrichmentRequest(
            company=p.get("company") or None,
            requested_tiers=["tier3"],
        ),
    ),
    (
        "jobspy",
        "JobSpy",
        "4",
        JobSpyEnricher,
        lambda p: EnrichmentRequest(
            job_search=p.get("job_search") or None,
            requested_tiers=["tier4"],
        ),
    ),
    (
        "local_business",
        "Local Business",
        "4",
        LocalBusinessEnricher,
        lambda p: EnrichmentRequest(
            business=p.get("business") or None,
            requested_tiers=["tier4"],
        ),
    ),
]

ENRICHER_SLUGS = {spec[0] for spec in ENRICHER_SPECS}


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


@dataclass
class CanaryCell:
    profile_id: str
    category: str
    enricher: str
    tier: str
    status: str  # PASS | FAIL | SKIP
    probe_status: str
    note: str = ""
    keys: list[str] = field(default_factory=list)


@dataclass
class CanaryProfileResult:
    profile_id: str
    category: str
    status: str  # PASS | FAIL | SKIP
    cells: list[CanaryCell] = field(default_factory=list)


# JobSpy pulls numpy/pandas; native Windows Python 3.13 + MINGW numpy can segfault.
JOBSPY_SUBPROCESS_TIMEOUT = 180.0
WINDOWS_JOBSPY_NOTE = (
    "skipped on native Windows (python-jobspy/numpy may segfault) - "
    "test in Docker/WSL or pass --include-jobspy"
)


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


def _profile_fields(entry: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in ("username", "email", "company", "job_search", "business"):
        value = str(entry.get(key) or "").strip()
        if value:
            out[key] = value
    return out


def load_canary_entries(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("canary file must be a JSON array")
    return raw


def resolve_enricher_slugs(entry: dict[str, Any], fields: dict[str, str]) -> list[str]:
    """Return enricher slugs to run for a profile row."""
    requested = entry.get("enrichers")
    if requested is None:
        slugs = [slug for slug, *_rest in ENRICHER_SPECS]
    else:
        if not isinstance(requested, list):
            raise ValueError("enrichers must be a list of slugs")
        slugs = [_slug(str(item)) for item in requested]

    selected: list[str] = []
    for slug in slugs:
        if slug not in ENRICHER_SLUGS:
            continue
        # Build a temporary request to see if validate could pass with fields present.
        # Still include slug; missing fields become SKIP at run time.
        selected.append(slug)
        _ = fields  # reserved for future field filtering clarity
    return selected


def build_tests_for_profile(
    fields: dict[str, str],
    *,
    enricher_slugs: list[str] | None = None,
) -> list[tuple[str, str, Enricher, EnrichmentRequest]]:
    """Build enricher probes; skip rows whose fields cannot form a valid request."""
    from pydantic import ValidationError

    allowed = set(enricher_slugs) if enricher_slugs is not None else ENRICHER_SLUGS
    tests: list[tuple[str, str, Enricher, EnrichmentRequest]] = []
    for slug, name, tier, factory, builder in ENRICHER_SPECS:
        if slug not in allowed:
            continue
        try:
            request = builder(fields)
        except ValidationError:
            # Profile listed an enricher without the identifiers that enricher needs.
            continue
        tests.append((name, tier, factory(), request))
    return tests


def skipped_enrichers_for_profile(
    fields: dict[str, str],
    *,
    enricher_slugs: list[str],
) -> list[tuple[str, str, str]]:
    """Return (slug, name, tier) for requested enrichers skipped due to invalid request."""
    from pydantic import ValidationError

    skipped: list[tuple[str, str, str]] = []
    allowed = set(enricher_slugs)
    for slug, name, tier, _factory, builder in ENRICHER_SPECS:
        if slug not in allowed:
            continue
        try:
            builder(fields)
        except ValidationError:
            skipped.append((slug, name, tier))
    return skipped


def build_tests() -> list[tuple[str, str, Enricher, EnrichmentRequest]]:
    return build_tests_for_profile(DEFAULT_PROFILE)


def score_probe_to_canary(probe_status: str, *, enricher: str = "") -> str:
    """Map isolation probe status to canary PASS/FAIL/SKIP."""
    if probe_status == "OK":
        return "PASS"
    if probe_status == "SKIP":
        return "SKIP"
    # Third-party WAF / GitHub rate limits / SERP empties are common in CI.
    if probe_status == "EMPTY" and enricher in {
        "jobspy",
        "gitrecon",
        "crosslinked",
        "theharvester",
        "maigret",
    }:
        return "SKIP"
    if probe_status in {"EMPTY", "CRASH"}:
        return "FAIL"
    return "SKIP"


def profile_status_from_cells(cells: list[CanaryCell]) -> str:
    if any(cell.status == "FAIL" for cell in cells):
        return "FAIL"
    if any(cell.status == "PASS" for cell in cells):
        return "PASS"
    return "SKIP"


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


async def probe_one(
    name: str,
    tier: str,
    enricher: Enricher,
    request: EnrichmentRequest,
    *,
    include_jobspy: bool = False,
) -> ProbeRow:
    settings = get_settings()
    slug = _slug(name)

    if slug == "jobspy" and sys.platform == "win32" and not include_jobspy:
        return ProbeRow(name=name, tier=tier, status="SKIP", note=WINDOWS_JOBSPY_NOTE)

    if not await enricher.validate(request):
        return ProbeRow(
            name=name,
            tier=tier,
            status="SKIP",
            note="validate() returned False - missing required request field",
        )

    if slug == "jobspy" and include_jobspy:
        status, fragment, note = _probe_jobspy_subprocess(request)
        return _row_from_fragment(name, tier, status, fragment, note)

    fragment = await enricher.run(request)
    status = "OK" if fragment else "EMPTY"
    return _row_from_fragment(
        name,
        tier,
        status,
        fragment,
        "" if fragment else _note_for_empty(name, settings),
    )


async def probe_enrichers(
    only: set[str] | None = None,
    *,
    include_jobspy: bool = False,
    skip: set[str] | None = None,
    tests: list[tuple[str, str, Enricher, EnrichmentRequest]] | None = None,
) -> list[ProbeRow]:
    rows: list[ProbeRow] = []
    skip = skip or set()
    suite = tests if tests is not None else build_tests()

    for name, tier, enricher, request in suite:
        slug = _slug(name)
        if only and slug not in only:
            continue
        if slug in skip:
            rows.append(
                ProbeRow(name=name, tier=tier, status="SKIP", note="excluded via --skip")
            )
            continue
        rows.append(
            await probe_one(
                name,
                tier,
                enricher,
                request,
                include_jobspy=include_jobspy,
            )
        )

    return rows


async def run_canary(
    entries: list[dict[str, Any]],
    *,
    only: set[str] | None = None,
    include_jobspy: bool = False,
    skip: set[str] | None = None,
    limit: int | None = None,
) -> list[CanaryProfileResult]:
    results: list[CanaryProfileResult] = []
    for index, entry in enumerate(entries):
        if limit is not None and index >= limit:
            break
        profile_id = str(entry.get("id") or f"profile-{index + 1}").strip()
        category = str(entry.get("category") or "unknown").strip()
        fields = _profile_fields(entry)
        try:
            slugs = resolve_enricher_slugs(entry, fields)
        except ValueError as exc:
            results.append(
                CanaryProfileResult(
                    profile_id=profile_id,
                    category=category,
                    status="FAIL",
                    cells=[
                        CanaryCell(
                            profile_id=profile_id,
                            category=category,
                            enricher="(config)",
                            tier="-",
                            status="FAIL",
                            probe_status="CRASH",
                            note=str(exc),
                        )
                    ],
                )
            )
            continue

        if only:
            slugs = [slug for slug in slugs if slug in only]
        if skip:
            slugs = [slug for slug in slugs if slug not in skip]

        cells: list[CanaryCell] = []
        if not slugs:
            cells.append(
                CanaryCell(
                    profile_id=profile_id,
                    category=category,
                    enricher="(none)",
                    tier="-",
                    status="SKIP",
                    probe_status="SKIP",
                    note="no enrichers selected or fields present",
                )
            )
        else:
            for slug, name, tier in skipped_enrichers_for_profile(fields, enricher_slugs=slugs):
                cells.append(
                    CanaryCell(
                        profile_id=profile_id,
                        category=category,
                        enricher=slug,
                        tier=tier,
                        status="SKIP",
                        probe_status="SKIP",
                        note=f"{name}: profile missing identifiers for EnrichmentRequest",
                    )
                )
            tests = build_tests_for_profile(fields, enricher_slugs=slugs)
            probes = await probe_enrichers(
                include_jobspy=include_jobspy,
                tests=tests,
            )
            for probe in probes:
                enricher_slug = _slug(probe.name)
                cells.append(
                    CanaryCell(
                        profile_id=profile_id,
                        category=category,
                        enricher=enricher_slug,
                        tier=probe.tier,
                        status=score_probe_to_canary(probe.status, enricher=enricher_slug),
                        probe_status=probe.status,
                        note=probe.note,
                        keys=list(probe.keys),
                    )
                )

        results.append(
            CanaryProfileResult(
                profile_id=profile_id,
                category=category,
                status=profile_status_from_cells(cells),
                cells=cells,
            )
        )
    return results


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


def print_canary(results: list[CanaryProfileResult]) -> None:
    print("\n== Tier 2–4 canary ==")
    fail_cells = 0
    for profile in results:
        print(f"\n{profile.status:4}  {profile.category:14} {profile.profile_id}")
        for cell in profile.cells:
            if cell.status == "FAIL":
                fail_cells += 1
            keys = ", ".join(cell.keys) if cell.keys else "-"
            note = f" - {cell.note}" if cell.note else ""
            print(
                f"  {cell.status:4}  tier{cell.tier}  {cell.enricher:<16} "
                f"probe={cell.probe_status} keys=[{keys}]{note}"
            )
    print(
        f"\nSummary: profiles "
        f"pass={sum(1 for r in results if r.status == 'PASS')} "
        f"fail={sum(1 for r in results if r.status == 'FAIL')} "
        f"skip={sum(1 for r in results if r.status == 'SKIP')} "
        f"| cell_fail={fail_cells}"
    )


def write_canary_report(results: list[CanaryProfileResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cells = [cell for profile in results for cell in profile.cells]
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "profiles": [
            {
                "id": profile.profile_id,
                "category": profile.category,
                "status": profile.status,
                "cells": [asdict(cell) for cell in profile.cells],
            }
            for profile in results
        ],
        "summary": {
            "profiles_pass": sum(1 for r in results if r.status == "PASS"),
            "profiles_fail": sum(1 for r in results if r.status == "FAIL"),
            "profiles_skip": sum(1 for r in results if r.status == "SKIP"),
            "cells_pass": sum(1 for c in cells if c.status == "PASS"),
            "cells_fail": sum(1 for c in cells if c.status == "FAIL"),
            "cells_skip": sum(1 for c in cells if c.status == "SKIP"),
        },
    }
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport written to {path}")


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
    parser.add_argument(
        "--canary",
        metavar="PATH",
        help="Run fixed profile canary JSON (PASS/FAIL/SKIP) instead of default samples",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="With --canary, only run the first N profiles",
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

    if args.canary:
        path = Path(args.canary)
        if not path.is_file():
            print(f"Canary file not found: {path}")
            return 1
        try:
            entries = load_canary_entries(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Invalid canary file: {exc}")
            return 1
        results = await run_canary(
            entries,
            only=only,
            include_jobspy=args.include_jobspy,
            skip=skip,
            limit=args.limit,
        )
        print_canary(results)
        if args.json:
            write_canary_report(results, RESULTS_DIR / "tier234-canary.json")
        fail_cells = sum(
            1 for profile in results for cell in profile.cells if cell.status == "FAIL"
        )
        return 0 if fail_cells == 0 else 1

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
        out_path = RESULTS_DIR / "probe-enrichers.json"
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nReport written to {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
