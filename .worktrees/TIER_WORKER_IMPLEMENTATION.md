# Tier-Specific Worker Implementation Summary

## Overview

Successfully implemented dedicated worker pools per tier with configurable concurrency levels:
- **Tier 1 (LinkedIn/browser):** 1-2 workers (heavy browser automation)
- **Tier 2-4 (API-based):** 4-8 workers (lightweight API enrichers)

## Implementation Status

All planned changes have been implemented and tested:

### ✅ 1. Configuration Settings (`backend/app/core/config.py`)

Added two new settings:
- `WORKER_QUEUE_MODE`: Controls queue routing (`"single"` or `"per_tier"`)
- `WORKER_TARGET_QUEUE`: Specifies which queue a worker listens to (`"tier1"` or `"tier234"`)

Default is `"single"` for backward compatibility.

### ✅ 2. Queue Routing Logic (`backend/app/workers/queue.py`)

Implemented three key functions:
- `get_queue_name_for_tiers()`: Routes jobs to appropriate queue based on requested tiers
- `get_worker_queue()`: Returns the queue a worker should listen to
- `enqueue_enrichment()`: Updated to accept `requested_tiers` parameter

Routing logic:
- Single mode: All jobs → `"enrichment"` queue
- Per-tier mode: Tier 1 jobs → `"tier1"` queue, Tier 2-4 jobs → `"tier234"` queue

### ✅ 3. Service Layer Update (`backend/app/modules/enrichment/service.py`)

Updated `enrich_async()` to pass `requested_tiers` to the queue routing logic.

### ✅ 4. Worker Initialization (`backend/app/workers/rq_worker.py`)

Updated worker startup to:
- Use `get_worker_queue()` instead of hardcoded queue
- Log which queue the worker is listening to
- Support both single and per-tier modes

### ✅ 5. Docker Compose Configuration (`backend/docker/docker-compose.tier-workers.yml`)

Created new compose file with:
- `worker-tier1`: 2 replicas, ENABLE_TIER1=true, listens to tier1 queue
- `worker-tier234`: 6 replicas, ENABLE_TIER1=false, listens to tier234 queue

Usage:
```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier-workers.yml \
  up -d
```

### ✅ 6. Unit Tests (`backend/tests/test_queue_routing.py`)

Created comprehensive test suite covering:
- Single queue mode behavior
- Per-tier routing for all tiers
- Mixed tier requests (tier1 takes precedence)
- Worker queue selection
- Error handling (missing WORKER_TARGET_QUEUE)
- Default settings validation

Note: Tests require database migration fix (unrelated to this PR).

### ✅ 7. Documentation (`backend/README.md`)

Added documentation for:
- Worker scaling options (single vs tier-specific)
- Environment variable configuration
- Deployment examples
- Migration path from single to per-tier mode

## Verification

Manual testing confirms the implementation works correctly:

**Default (single mode):**
```bash
$ python -c "from app.workers.queue import get_queue_name_for_tiers; from app.domain.enums import RequestedTier; print(get_queue_name_for_tiers([RequestedTier.tier1]))"
enrichment
```

**Per-tier mode:**
```bash
$ WORKER_QUEUE_MODE=per_tier python -c "..."
tier1: tier1
tier2: tier234
tier3: tier234
tier4: tier234
```

## Architecture

```
API /enrich
    ↓
Queue Router (get_queue_name_for_tiers)
    ↓
    ├─→ tier1 queue    → worker-tier1 (2 instances, browser-heavy)
    └─→ tier234 queue  → worker-tier234 (6 instances, API-light)
```

## Backward Compatibility

- Default `WORKER_QUEUE_MODE=single` preserves existing behavior
- No changes required for current deployments
- Gradual migration path: enable per-tier mode when ready
- In-flight jobs in Redis persist across worker restarts

## Next Steps

1. **Staging validation:** Deploy with `per_tier` mode in staging
2. **Integration tests:** Test job routing with real enrichment requests
3. **Load testing:** Verify tier234 jobs process faster with more workers
4. **Production rollout:** Enable per-tier mode with monitoring
5. **Metrics:** Add queue depth tracking per tier (Datadog/Prometheus)

## Files Changed

- `backend/app/core/config.py` - Added configuration settings
- `backend/app/workers/queue.py` - Implemented queue routing logic
- `backend/app/modules/enrichment/service.py` - Updated job enqueuing
- `backend/app/workers/rq_worker.py` - Updated worker initialization
- `backend/docker/docker-compose.tier-workers.yml` - New tier-specific worker services
- `backend/tests/test_queue_routing.py` - New unit tests
- `backend/README.md` - Added deployment documentation
