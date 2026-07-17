"""Unit tests for Tier 2–4 probe canary helpers (no live CLIs / sidecars)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BACKEND / "scripts" / "probe_enrichers.py"
EXAMPLE_PATH = BACKEND / "docs" / "tier234_canary_set.example.json"


def _load_probe_module():
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    name = "probe_enrichers_canary"
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


probe = _load_probe_module()


def test_example_canary_has_twenty_entries() -> None:
    entries = probe.load_canary_entries(EXAMPLE_PATH)
    assert len(entries) == 20
    for entry in entries:
        assert entry.get("id")
        assert entry.get("category")
        assert isinstance(entry.get("enrichers"), list)
        assert entry["enrichers"]


def test_build_tests_for_profile_filters_by_slug() -> None:
    fields = {"username": "alice", "company": "Acme"}
    tests = probe.build_tests_for_profile(fields, enricher_slugs=["sherlock", "crosslinked"])
    names = [name for name, *_rest in tests]
    assert names == ["Sherlock", "CrossLinked"]


def test_resolve_enricher_slugs_honors_list() -> None:
    entry = {"enrichers": ["Sherlock", "email-verify"]}
    slugs = probe.resolve_enricher_slugs(entry, {"username": "x", "email": "a@b.com"})
    assert slugs == ["sherlock", "email_verify"]


def test_resolve_enricher_slugs_defaults_to_catalog() -> None:
    slugs = probe.resolve_enricher_slugs({}, {"username": "x"})
    assert set(slugs) == probe.ENRICHER_SLUGS


def test_score_probe_to_canary() -> None:
    assert probe.score_probe_to_canary("OK") == "PASS"
    assert probe.score_probe_to_canary("EMPTY") == "FAIL"
    assert probe.score_probe_to_canary("CRASH") == "FAIL"
    assert probe.score_probe_to_canary("SKIP") == "SKIP"
    assert probe.score_probe_to_canary("EMPTY", enricher="jobspy") == "SKIP"
    assert probe.score_probe_to_canary("EMPTY", enricher="gitrecon") == "SKIP"
    assert probe.score_probe_to_canary("EMPTY", enricher="crosslinked") == "SKIP"
    assert probe.score_probe_to_canary("EMPTY", enricher="theharvester") == "SKIP"
    assert probe.score_probe_to_canary("EMPTY", enricher="maigret") == "SKIP"
    assert probe.score_probe_to_canary("CRASH", enricher="jobspy") == "FAIL"


def test_build_tests_skips_invalid_request_fields() -> None:
    # theharvester needs company or email; business-only must not raise.
    tests = probe.build_tests_for_profile(
        {"business": "warehouse Austin TX"},
        enricher_slugs=["theharvester", "local_business"],
    )
    names = [name for name, *_rest in tests]
    assert names == ["Local Business"]
    skipped = probe.skipped_enrichers_for_profile(
        {"business": "warehouse Austin TX"},
        enricher_slugs=["theharvester", "local_business"],
    )
    assert [slug for slug, *_ in skipped] == ["theharvester"]


def test_profile_status_from_cells() -> None:
    fail = probe.CanaryCell(
        profile_id="p",
        category="technical",
        enricher="sherlock",
        tier="2",
        status="FAIL",
        probe_status="EMPTY",
    )
    pas = probe.CanaryCell(
        profile_id="p",
        category="technical",
        enricher="maigret",
        tier="2",
        status="PASS",
        probe_status="OK",
    )
    skip = probe.CanaryCell(
        profile_id="p",
        category="technical",
        enricher="jobspy",
        tier="4",
        status="SKIP",
        probe_status="SKIP",
    )
    assert probe.profile_status_from_cells([pas, fail]) == "FAIL"
    assert probe.profile_status_from_cells([pas, skip]) == "PASS"
    assert probe.profile_status_from_cells([skip]) == "SKIP"


def test_profile_fields_strips_empty() -> None:
    fields = probe._profile_fields(
        {"username": " a ", "email": "", "company": None, "job_search": "se"}
    )
    assert fields == {"username": "a", "job_search": "se"}


def test_build_tests_default_matches_catalog_size() -> None:
    tests = probe.build_tests()
    assert len(tests) == len(probe.ENRICHER_SPECS)
