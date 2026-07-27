"""Tests for parallel tier execution"""

import asyncio
import time
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import RequestedTier
from app.enrichers.pipeline import Pipeline


@pytest.mark.asyncio
async def test_all_tiers_run_in_parallel(db_session: AsyncSession):
    """Verify all tiers execute simultaneously rather than sequentially"""
    pipeline = Pipeline(db_session)
    request = EnrichmentRequest(
        username="test-user",
        linkedin_url="https://linkedin.com/in/test-user",
        company="TestCorp",
        requested_tiers=[
            RequestedTier.tier1,
            RequestedTier.tier2,
            RequestedTier.tier3,
            RequestedTier.tier4,
        ],
    )

    # Mock each tier to take a specific amount of time
    async def mock_tier1(req):
        await asyncio.sleep(0.2)  # 200ms
        return {"payloads": [{"photo": "test1.jpg"}], "duration": 0.2}

    async def mock_tier2(req):
        await asyncio.sleep(0.1)  # 100ms
        return {"payloads": [{"handles": []}], "duration": 0.1}

    async def mock_tier3(req):
        await asyncio.sleep(0.3)  # 300ms (longest)
        return {"payloads": [{"emails": []}], "duration": 0.3}

    async def mock_tier4(req):
        await asyncio.sleep(0.15)  # 150ms
        return {"payloads": [{"jobs": []}], "duration": 0.15}

    with (
        patch.object(pipeline, "_run_tier1_task", side_effect=mock_tier1),
        patch.object(pipeline, "_run_tier2_task", side_effect=mock_tier2),
        patch.object(pipeline, "_run_tier3_task", side_effect=mock_tier3),
        patch.object(pipeline, "_run_tier4_task", side_effect=mock_tier4),
    ):
        start = time.time()
        payloads = await pipeline._dispatch(request, sync_mode=False)
        elapsed = time.time() - start

        # If parallel: elapsed should be ~max(0.2, 0.1, 0.3, 0.15) = ~0.3s
        # If sequential: elapsed would be 0.2 + 0.1 + 0.3 + 0.15 = 0.75s
        # Allow some overhead, so check elapsed < 0.5s
        assert elapsed < 0.5, f"Tiers ran sequentially (took {elapsed}s), expected parallel (<0.5s)"
        assert len(payloads) == 4, "Should have payloads from all 4 tiers"


@pytest.mark.asyncio
async def test_partial_tier_failure_returns_results(db_session: AsyncSession):
    """Verify partial results returned when some tiers fail"""
    pipeline = Pipeline(db_session)
    request = EnrichmentRequest(
        username="test-user",
        requested_tiers=[
            RequestedTier.tier1,
            RequestedTier.tier2,
            RequestedTier.tier3,
        ],
    )

    async def mock_tier1_success(req):
        return {"payloads": [{"photo": "success.jpg"}], "duration": 0.1}

    async def mock_tier2_failure(req):
        raise ConnectionError("Tier 2 network error")

    async def mock_tier3_success(req):
        return {"payloads": [{"emails": ["test@example.com"]}], "duration": 0.2}

    with (
        patch.object(pipeline, "_run_tier1_task", side_effect=mock_tier1_success),
        patch.object(pipeline, "_run_tier2_task", side_effect=mock_tier2_failure),
        patch.object(pipeline, "_run_tier3_task", side_effect=mock_tier3_success),
    ):
        payloads = await pipeline._dispatch(request, sync_mode=False)

        # Should have results from tier1 and tier3, but not tier2
        assert len(payloads) == 2, "Should have payloads from 2 successful tiers"

        # Check metadata includes failed tiers
        if payloads and payloads[0].get("metadata"):
            failed_tiers = payloads[0]["metadata"]["tier_execution"]["failed_tiers"]
            assert "tier2" in failed_tiers, "Failed tier should be tracked in metadata"


@pytest.mark.asyncio
async def test_retry_logic_on_transient_failure(db_session: AsyncSession):
    """Verify transient failures trigger retries with exponential backoff"""
    pipeline = Pipeline(db_session)

    # Mock enricher that fails twice then succeeds
    mock_enricher = Mock()
    mock_enricher.source_name = "test-enricher"

    call_count = 0

    async def mock_invoke_enricher(enricher, request):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise TimeoutError("Temporary timeout")
        return {"result": "success"}

    with patch.object(pipeline, "_invoke_enricher", side_effect=mock_invoke_enricher):
        result = await pipeline._invoke_enricher_with_retry(
            mock_enricher, EnrichmentRequest(username="test")
        )

        assert call_count == 3, "Should attempt 3 times (2 failures + 1 success)"
        assert result == {"result": "success"}, "Should return success on third attempt"


@pytest.mark.asyncio
async def test_permanent_failure_no_retry(db_session: AsyncSession):
    """Verify permanent errors fail immediately without retry"""
    pipeline = Pipeline(db_session)

    mock_enricher = Mock()
    mock_enricher.source_name = "test-enricher"

    call_count = 0

    async def mock_invoke_enricher(enricher, request):
        nonlocal call_count
        call_count += 1
        raise ValueError("Permanent validation error")

    with patch.object(pipeline, "_invoke_enricher", side_effect=mock_invoke_enricher):
        result = await pipeline._invoke_enricher_with_retry(
            mock_enricher, EnrichmentRequest(username="test")
        )

        assert call_count == 1, "Should only attempt once for permanent errors"
        assert result == {}, "Should return empty dict on permanent failure"


@pytest.mark.asyncio
async def test_tier_execution_metadata_added(db_session: AsyncSession):
    """Verify execution metadata is added to payloads"""
    pipeline = Pipeline(db_session)
    request = EnrichmentRequest(
        username="test-user",
        requested_tiers=[RequestedTier.tier2, RequestedTier.tier4],
    )

    async def mock_tier2(req):
        return {"payloads": [{"handles": []}], "duration": 0.15}

    async def mock_tier4(req):
        return {"payloads": [{"jobs": []}], "duration": 0.25}

    with (
        patch.object(pipeline, "_run_tier2_task", side_effect=mock_tier2),
        patch.object(pipeline, "_run_tier4_task", side_effect=mock_tier4),
    ):
        payloads = await pipeline._dispatch(request, sync_mode=False)

        # Check metadata exists
        assert len(payloads) > 0
        assert "metadata" in payloads[0]

        tier_execution = payloads[0]["metadata"]["tier_execution"]
        assert tier_execution["parallel"] is True
        assert "tier2" in tier_execution["timings"]
        assert "tier4" in tier_execution["timings"]
        assert tier_execution["timings"]["tier2"] == 0.15
        assert tier_execution["timings"]["tier4"] == 0.25


@pytest.mark.asyncio
async def test_sync_mode_skips_tier1(db_session: AsyncSession):
    """Verify sync mode excludes tier1 (browser-based)"""
    pipeline = Pipeline(db_session)
    request = EnrichmentRequest(
        username="test-user",
        requested_tiers=[
            RequestedTier.tier1,
            RequestedTier.tier2,
        ],
    )

    tier1_called = False
    tier2_called = False

    async def mock_tier1(req):
        nonlocal tier1_called
        tier1_called = True
        return {"payloads": [{"photo": "test.jpg"}], "duration": 0.1}

    async def mock_tier2(req):
        nonlocal tier2_called
        tier2_called = True
        return {"payloads": [{"handles": []}], "duration": 0.1}

    with (
        patch.object(pipeline, "_run_tier1_task", side_effect=mock_tier1),
        patch.object(pipeline, "_run_tier2_task", side_effect=mock_tier2),
    ):
        await pipeline._dispatch(request, sync_mode=True)

        assert not tier1_called, "Tier 1 should not be called in sync mode"
        assert tier2_called, "Tier 2 should be called in sync mode"
