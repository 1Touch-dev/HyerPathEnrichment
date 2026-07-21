"""Validate Prometheus alert rules YAML parses and references known metrics."""

from __future__ import annotations

from pathlib import Path

import pytest

RULES_PATH = Path(__file__).resolve().parents[1] / "observability" / "alerts" / "hyrepath.rules.yml"

# Metric / selector names that must appear in the rules file (existing /metrics surface).
EXPECTED_METRIC_SNIPPETS = (
    "up{",
    "tier1_scrape_total",
    "tier1_upload_total",
    "tier1_profile_pool_exhausted_total",
)

EXPECTED_ALERTS = (
    "HyrepathApiDown",
    "HyrepathTier1ScrapeErrorRate",
    "HyrepathTier1UploadErrors",
    "HyrepathTier1ProfilePoolExhausted",
    "HyrepathQueueDepthHigh",
    "HyrepathQueueFailuresHigh",
)


def test_prometheus_rules_file_exists() -> None:
    assert RULES_PATH.is_file(), f"missing rules file: {RULES_PATH}"


def test_prometheus_rules_yaml_parses() -> None:
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "groups" in data
    assert isinstance(data["groups"], list)
    assert data["groups"], "expected at least one rule group"

    alert_names: list[str] = []
    for group in data["groups"]:
        assert "name" in group
        assert "rules" in group
        for rule in group["rules"]:
            assert "alert" in rule
            assert "expr" in rule
            assert "labels" in rule
            alert_names.append(rule["alert"])

    for name in EXPECTED_ALERTS:
        assert name in alert_names, f"missing alert {name}"


def test_prometheus_rules_reference_known_metrics() -> None:
    text = RULES_PATH.read_text(encoding="utf-8")
    for snippet in EXPECTED_METRIC_SNIPPETS:
        assert snippet in text, f"expected metric snippet {snippet!r} in rules"
