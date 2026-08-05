# Docker Stack Rebuild Instructions

## Configuration Changes Applied

The following files have been updated on branch `feature/selective-proxy-multi-workers`:

1. **backend/docker/docker-compose.tier-workers.yml**
   - Added `network_mode: host` to `worker-tier1`
   - Set `PROXY_MODE: none` for `worker-tier1` (no proxy for LinkedIn)
   - Set `PROXY_MODE: paid` for `worker-tier234` (Oxylabs proxy for tiers 2-4)
   - Updated all service URLs to use `127.0.0.1` for host networking

2. **backend/.env.production**
   - Changed `WORKER_QUEUE_MODE=per_tier` (was: `single`)

## Rebuild Command

Execute this command in your WSL terminal:

```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

# Stop existing containers
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.multilogin.yml \
  -f docker-compose.tier-workers.yml \
  --env-file ../.env.production \
  down

# Rebuild and start with new configuration
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.multilogin.yml \
  -f docker-compose.tier-workers.yml \
  --env-file ../.env.production \
  up -d --build
```

## Verification Commands

### Check worker logs for proxy configuration:

```bash
# Tier1 worker should show PROXY_MODE=none
docker logs hyrepath-worker-tier1-1 2>&1 | head -50

# Tier234 worker should show PROXY_MODE=paid
docker logs hyrepath-worker-tier234-1 2>&1 | head -50
```

### Check container status:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.multilogin.yml \
  -f docker-compose.tier-workers.yml \
  --env-file ../.env.production \
  ps
```

## Next Steps

After rebuilding, test with the 3 LinkedIn profiles:
1. https://www.linkedin.com/in/diwakarmishra4/
2. https://www.linkedin.com/in/sumit-kumar-24a9a31a2/
3. https://www.linkedin.com/in/anjali-horo-64166970/

**Only create PR if all 3 profiles successfully return photo images.**
