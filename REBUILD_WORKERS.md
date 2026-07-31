# Rebuild Worker Containers After Removing Debug Code

The debug instrumentation code has been removed from all backend files. Now you need to rebuild the worker containers.

## Rebuild Command

Run this in your WSL terminal:

```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

# Rebuild ONLY the worker containers (faster than full rebuild)
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.multilogin.yml \
  -f docker-compose.tier-workers.yml \
  --env-file ../.env.production \
  up -d --build worker-tier1 worker-tier234
```

This will:
1. Rebuild only the worker images (tier1 and tier234)
2. Restart the worker containers with clean code
3. Keep all other services running

## After Rebuild

Run the test again:

```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment
bash test-tier1-only.sh
```

All 3 profiles should now return photos successfully!
