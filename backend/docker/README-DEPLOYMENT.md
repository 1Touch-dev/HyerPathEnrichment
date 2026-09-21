# Production Deployment

## Sequential Worker Startup (Recommended)

To avoid proxy rate limiting, workers start sequentially with a configurable delay:

```bash
bash backend/scripts/start_production.sh --with-linux-mlx
```

That supported Linux MLX path starts:
- `worker` for auxiliary queues (`outreach_generation`, `linkedin_send_batch`, `audio_cleanup`, feedback/question generation, document queues)
- `worker-email` for the `email` queue
- `worker-cleanup` for orphan-job maintenance
- `worker-job-matching` for the dedicated `job_matching` queue and scheduler seeding
- `worker-tier234` for `tier234`
- `worker-tier1` plus `multilogin` for Tier 1

Do **not** reconstruct the old `docker-compose.tier1.yml + docker-compose.multilogin.yml`
family directly. The supported Linux path is `docker-compose.prod.yml +
docker-compose.foundation.yml + docker-compose.tier-workers.yml +
docker-compose.multilogin.yml`, or the script above.

## Configuration

Edit `.env.production`:

- `WORKER_TIER234_COUNT=6` - Number of tier234 workers (adjust based on load)
- `WORKER_STARTUP_DELAY=10` - Optional seconds between startup of bridge-network workers that use `entrypoint-worker.sh` (`worker`, scaled `worker-tier234`, `worker-email` if scaled)

## Monitoring Startup

Watch workers start sequentially:

```bash
docker compose logs -f worker-tier234 | grep "Worker #"
```

Expected output:
```
worker-tier234-1  | Worker #1: Starting RQ worker now!
worker-tier234-2  | Worker #2: Waiting 10 seconds before starting...
worker-tier234-3  | Worker #3: Waiting 20 seconds before starting...
...
```

## Testing Proxy Connectivity

After all workers have started, test from one container:

```bash
docker exec docker-worker-tier234-1 curl -x pr.oxylabs.io:7777 \
  -U YOUR_USERNAME:YOUR_PASSWORD https://httpbin.org/ip
```

Expected: Should return proxy IP, not "503 Service Temporarily Unavailable".

## Troubleshooting

### Workers not starting sequentially

Check that the entrypoint script has correct line endings:

```bash
docker exec docker-worker-tier234-1 cat /entrypoint-worker.sh | od -c
```

Should show `\n` (LF) not `\r\n` (CRLF).

### Proxy still returning 503

Try increasing the delay:

```bash
# In .env.production
WORKER_STARTUP_DELAY=15  # or 20
```

Then restart with the supported script:

```bash
bash backend/scripts/start_production.sh --with-linux-mlx
```

## Full Restart

To completely restart the backend with fresh containers:

```bash
cd backend/docker

# Stop and remove all containers
bash backend/scripts/start_production.sh --down --with-linux-mlx

# Rebuild worker image
docker compose --env-file ../.env.production build --no-cache worker

# Start everything
bash backend/scripts/start_production.sh --with-linux-mlx
```
