# Rebuild Worker Containers On The Supported Linux MLX Path

The debug instrumentation code has been removed from all backend files. Now you need to rebuild the worker containers.

## Rebuild Command

Run this on a real Linux host (or your Linux production VM):

```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

# Rebuild only the supported worker containers for the Linux MLX topology
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.foundation.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.multilogin.yml \
  --env-file ../.env.production \
  up -d --build worker worker-email worker-cleanup worker-job-matching worker-tier234 worker-tier1 multilogin
```

This will:
1. Rebuild the supported worker images (`worker`, `worker-email`, `worker-cleanup`, `worker-job-matching`, `worker-tier234`, `worker-tier1`)
2. Restart those containers with clean code
3. Keep all other services running

## After Rebuild

Run the test again:

```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment
bash test-tier1-only.sh
```

All 3 profiles should now return photos successfully!
