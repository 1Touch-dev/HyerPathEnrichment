# Production Deployment

## Sequential Worker Startup (Recommended)

To avoid proxy rate limiting, workers start sequentially with a configurable delay:

```bash
cd backend/docker

# Build worker image with entrypoint
docker compose --env-file ../.env.production build worker

# Start all services with scaled tier234 workers
docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  up -d --scale worker-tier234=${WORKER_TIER234_COUNT:-6}
```

## Configuration

Edit `.env.production`:

- `WORKER_TIER234_COUNT=6` - Number of tier234 workers (adjust based on load)
- `WORKER_STARTUP_DELAY=10` - Seconds between worker startups (increase if proxy still rate limits)

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
  -U axiz666_1NwOV:Oxylab+axiz6040 https://httpbin.org/ip
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

Then rebuild and restart:

```bash
docker compose build --no-cache worker
docker compose up -d --scale worker-tier234=6
```

## Full Restart

To completely restart the backend with fresh containers:

```bash
cd backend/docker

# Stop and remove all containers
docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  down

# Rebuild worker image
docker compose --env-file ../.env.production build --no-cache worker

# Start everything
docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  up -d --scale worker-tier234=${WORKER_TIER234_COUNT:-6}
```
