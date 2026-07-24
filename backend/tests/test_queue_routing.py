"""Tests for queue routing logic in tier-specific worker architecture."""

import pytest

from app.core.config import get_settings
from app.domain.enums import RequestedTier
from app.workers.queue import get_queue_name_for_tiers, get_worker_queue


def test_single_queue_mode_tier1(monkeypatch: pytest.MonkeyPatch) -> None:
    """WORKER_QUEUE_MODE=single should always use 'enrichment' queue for tier1."""
    monkeypatch.setenv("WORKER_QUEUE_MODE", "single")
    # Force reload of settings
    get_settings.cache_clear()

    queue_name = get_queue_name_for_tiers([RequestedTier.tier1])
    assert queue_name == "enrichment"


def test_single_queue_mode_tier234(monkeypatch: pytest.MonkeyPatch) -> None:
    """WORKER_QUEUE_MODE=single should always use 'enrichment' queue for tier2-4."""
    monkeypatch.setenv("WORKER_QUEUE_MODE", "single")
    get_settings.cache_clear()

    assert get_queue_name_for_tiers([RequestedTier.tier2]) == "enrichment"
    assert get_queue_name_for_tiers([RequestedTier.tier3]) == "enrichment"
    assert get_queue_name_for_tiers([RequestedTier.tier4]) == "enrichment"


def test_per_tier_routing_tier1(monkeypatch: pytest.MonkeyPatch) -> None:
    """WORKER_QUEUE_MODE=per_tier routes tier1 jobs to 'tier1' queue."""
    monkeypatch.setenv("WORKER_QUEUE_MODE", "per_tier")
    get_settings.cache_clear()

    queue_name = get_queue_name_for_tiers([RequestedTier.tier1])
    assert queue_name == "tier1"


def test_per_tier_routing_tier234(monkeypatch: pytest.MonkeyPatch) -> None:
    """WORKER_QUEUE_MODE=per_tier routes tier2-4 jobs to 'tier234' queue."""
    monkeypatch.setenv("WORKER_QUEUE_MODE", "per_tier")
    get_settings.cache_clear()

    assert get_queue_name_for_tiers([RequestedTier.tier2]) == "tier234"
    assert get_queue_name_for_tiers([RequestedTier.tier3]) == "tier234"
    assert get_queue_name_for_tiers([RequestedTier.tier4]) == "tier234"


def test_per_tier_routing_multiple_tiers_tier234(monkeypatch: pytest.MonkeyPatch) -> None:
    """Multiple tier2-4 requests go to 'tier234' queue."""
    monkeypatch.setenv("WORKER_QUEUE_MODE", "per_tier")
    get_settings.cache_clear()

    queue_name = get_queue_name_for_tiers([RequestedTier.tier2, RequestedTier.tier3])
    assert queue_name == "tier234"

    queue_name = get_queue_name_for_tiers([RequestedTier.tier3, RequestedTier.tier4])
    assert queue_name == "tier234"


def test_per_tier_routing_mixed_tiers_tier1_takes_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When tier1 is mixed with tier2-4, tier1 queue takes precedence."""
    monkeypatch.setenv("WORKER_QUEUE_MODE", "per_tier")
    get_settings.cache_clear()

    queue_name = get_queue_name_for_tiers([RequestedTier.tier1, RequestedTier.tier2])
    assert queue_name == "tier1"

    queue_name = get_queue_name_for_tiers(
        [RequestedTier.tier1, RequestedTier.tier2, RequestedTier.tier3]
    )
    assert queue_name == "tier1"


def test_per_tier_routing_empty_tiers_defaults_to_tier234(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty tier list should default to tier234 in per_tier mode."""
    monkeypatch.setenv("WORKER_QUEUE_MODE", "per_tier")
    get_settings.cache_clear()

    queue_name = get_queue_name_for_tiers([])
    assert queue_name == "tier234"


def test_get_worker_queue_single_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Worker in single mode listens to 'enrichment' queue."""
    monkeypatch.setenv("WORKER_QUEUE_MODE", "single")
    get_settings.cache_clear()

    queue = get_worker_queue()
    assert queue.name == "enrichment"


def test_get_worker_queue_per_tier_mode_tier1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Worker in per_tier mode with WORKER_TARGET_QUEUE=tier1 listens to tier1 queue."""
    monkeypatch.setenv("WORKER_QUEUE_MODE", "per_tier")
    monkeypatch.setenv("WORKER_TARGET_QUEUE", "tier1")
    get_settings.cache_clear()

    queue = get_worker_queue()
    assert queue.name == "tier1"


def test_get_worker_queue_per_tier_mode_tier234(monkeypatch: pytest.MonkeyPatch) -> None:
    """Worker in per_tier mode with WORKER_TARGET_QUEUE=tier234 listens to tier234 queue."""
    monkeypatch.setenv("WORKER_QUEUE_MODE", "per_tier")
    monkeypatch.setenv("WORKER_TARGET_QUEUE", "tier234")
    get_settings.cache_clear()

    queue = get_worker_queue()
    assert queue.name == "tier234"


def test_get_worker_queue_per_tier_mode_missing_target_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker in per_tier mode without WORKER_TARGET_QUEUE raises ValueError."""
    monkeypatch.setenv("WORKER_QUEUE_MODE", "per_tier")
    monkeypatch.delenv("WORKER_TARGET_QUEUE", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="WORKER_TARGET_QUEUE required"):
        get_worker_queue()


def test_default_queue_mode_is_single() -> None:
    """Default WORKER_QUEUE_MODE should be 'single' for backward compatibility."""
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.worker_queue_mode == "single"
