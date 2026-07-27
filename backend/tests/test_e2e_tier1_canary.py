"""Unit tests for Tier 1 API canary helpers (no live Multilogin / LinkedIn)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Self
from unittest.mock import MagicMock

import httpx
import pytest

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BACKEND / "scripts" / "e2e_tier1_canary.py"
EXAMPLE_PATH = BACKEND / "docs" / "tier1_canary_set.example.json"


def _load_canary_module():
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    name = "e2e_tier1_canary"
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


canary = _load_canary_module()


def test_example_canary_has_twenty_valid_entries() -> None:
    entries = canary.load_canary_entries(EXAMPLE_PATH)
    assert len(entries) == 20
    profiles, skips = canary.build_profiles(entries, limit=None)
    assert skips == []
    assert len(profiles) == 20
    for profile in profiles:
        assert profile.slug
        assert profile.linkedin_url.startswith("https://www.linkedin.com/in/")
        assert profile.category in {"technical", "non-technical", "private"}


def test_default_expect_photo_by_category() -> None:
    assert canary.default_expect_photo("technical") is True
    assert canary.default_expect_photo("non-technical") is True
    assert canary.default_expect_photo("private") is False
    assert canary.default_expect_photo("private", explicit=True) is True
    assert canary.default_expect_photo("technical", explicit=False) is False


def test_parse_canary_profile_skip_invalid() -> None:
    profile, reason = canary.parse_canary_profile({"category": "technical"})
    assert profile is None
    assert "missing" in reason


def test_score_job_payload_expect_photo_pass() -> None:
    job = {
        "status": "completed",
        "dossier": {
            "photo": {"asset_url": "file:///tmp/photo.jpg", "source": "linkedin-photo"},
            "sources": ["linkedin-photo"],
        },
    }
    status, detail = canary.score_job_payload(job, expect_photo=True)
    assert status == "PASS"
    assert "photo ok" in detail


def test_score_job_payload_expect_photo_fail_missing() -> None:
    job = {"status": "completed", "dossier": {"photo": None, "sources": []}}
    status, detail = canary.score_job_payload(job, expect_photo=True)
    assert status == "FAIL"
    assert "asset_url" in detail


def test_score_job_payload_private_pass_without_photo() -> None:
    job = {"status": "completed", "dossier": {"photo": None, "sources": []}}
    status, detail = canary.score_job_payload(job, expect_photo=False)
    assert status == "PASS"
    assert "without photo" in detail


def test_score_job_payload_failed_status() -> None:
    status, _ = canary.score_job_payload({"status": "failed", "dossier": {}}, expect_photo=True)
    assert status == "FAIL"


def test_score_job_payload_timeout_still_queued() -> None:
    status, detail = canary.score_job_payload(
        {"status": "queued", "dossier": {}},
        expect_photo=True,
    )
    assert status == "FAIL"
    assert "timeout" in detail


def test_sync_guard_rejects_photo() -> None:
    ok, detail = canary.sync_guard_ok(
        {"dossier": {"photo": {"asset_url": "x"}, "sources": ["linkedin-photo"]}}
    )
    assert ok is False
    assert "photo" in detail.lower() or "tier 1" in detail.lower()


def test_sync_guard_accepts_empty() -> None:
    ok, detail = canary.sync_guard_ok({"dossier": {"photo": None, "sources": ["Sherlock"]}})
    assert ok is True
    assert "skipped" in detail


@pytest.mark.asyncio
async def test_run_profile_happy_path_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = canary.CanaryProfile(
        slug="your-tech-slug-01",
        linkedin_url="https://www.linkedin.com/in/your-tech-slug-01",
        category="technical",
        expect_photo=True,
    )
    runner = canary.Tier1ApiCanary(base_url="http://test", token="token")

    enqueue_resp = MagicMock()
    enqueue_resp.status_code = 202
    enqueue_resp.json.return_value = {"id": "job-1"}

    poll_resp = MagicMock()
    poll_resp.json.return_value = {
        "id": "job-1",
        "status": "completed",
        "dossier": {
            "photo": {"asset_url": "file:///cache/example.jpg"},
            "sources": ["linkedin-photo"],
        },
    }

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: Any, **kwargs: Any) -> MagicMock:
            return enqueue_resp

        async def get(self, *args: Any, **kwargs: Any) -> MagicMock:
            return poll_resp

    monkeypatch.setattr(canary.httpx, "AsyncClient", FakeClient)
    row = await runner.run_profile(profile)
    assert row.status == "PASS"
    assert row.job_id == "job-1"
    assert row.asset_url == "file:///cache/example.jpg"


@pytest.mark.asyncio
async def test_check_health_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = canary.Tier1ApiCanary(base_url="http://test", token="token")

    class BoomClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, *args: Any, **kwargs: Any) -> None:
            raise httpx.ConnectError("refused")

    monkeypatch.setattr(canary.httpx, "AsyncClient", BoomClient)
    await runner.check_health()
    assert runner.checks[-1].ok is False
