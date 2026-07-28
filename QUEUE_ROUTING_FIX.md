# Queue Routing Fix - Job Stuck in "queued" Status

## Problem
Jobs were stuck in "queued" status for 7+ minutes instead of being processed within 10-20 seconds.

## Root Cause
**Queue routing mismatch** between API and workers:
- **API service**: Using default `WORKER_QUEUE_MODE=single`, enqueuing jobs to `enrichment` queue
- **Worker services**: Configured with `WORKER_QUEUE_MODE=per_tier`, listening to `tier1` and `tier234` queues
- **Result**: Jobs sent to wrong queue, workers never picked them up

## Fix Applied

### 1. Updated `docker-compose.yml`
Added `WORKER_QUEUE_MODE` configuration to API service (line 23-24):
```yaml
environment:
  # ... existing vars ...
  # Worker queue routing - must match tier-workers configuration
  WORKER_QUEUE_MODE: ${WORKER_QUEUE_MODE:-per_tier}
```

### 2. Updated `.env.production`
Added explicit configuration:
```bash
WORKER_QUEUE_MODE=per_tier
```

## How to Apply the Fix

### Option 1: Restart API Only (Faster)
```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker
docker compose --env-file ../.env.production restart api
```

### Option 2: Full Restart (If restart doesn't pick up env changes)
```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker
docker compose --env-file ../.env.production up -d --force-recreate api
```

## Verification

After restarting the API:

1. **Check API picked up the config:**
   ```bash
   docker compose logs api | grep -i "queue"
   ```

2. **Create a new test job** and verify it moves from "queued" to "running" within 10-20 seconds

3. **Check Redis queues** to see jobs are being distributed correctly:
   ```bash
   docker exec docker-redis-1 redis-cli
   > LLEN tier1
   > LLEN tier234
   > LLEN enrichment
   ```

4. **Check worker logs** to see if they're picking up jobs:
   ```bash
   docker compose logs worker-tier1 --tail=50
   docker compose logs worker-tier234 --tail=50
   ```

## Expected Behavior After Fix

When `WORKER_QUEUE_MODE=per_tier`:
- **Jobs with tier1 + (tier2/3/4)**: Creates parent-child pattern, enqueues to both `tier1` and `tier234` queues
- **Jobs with only tier2/3/4**: Enqueues to `tier234` queue
- **Jobs with only tier1**: Enqueues to `tier1` queue

Workers listening to their respective queues will pick up and process jobs immediately.

## Files Modified
- `backend/docker/docker-compose.yml` - Added WORKER_QUEUE_MODE to API service
- `backend/.env.production` - Added WORKER_QUEUE_MODE=per_tier
