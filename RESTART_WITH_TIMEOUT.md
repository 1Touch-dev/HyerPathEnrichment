# Restart Supported Linux MLX Workers With Increased Timeout

The browser timeout has been increased from 45s to 90s to handle slow LinkedIn page loads.

## Restart Command

Run this on the supported Linux MLX host:

```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.foundation.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.multilogin.yml \
  --env-file ../.env.production \
  restart worker worker-email worker-cleanup worker-job-matching worker-tier1 worker-tier234 multilogin
```

## Test Again

After restart, test the 3 profiles:

```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment
bash test-tier1-only.sh
```

The increased timeout should allow LinkedIn pages to load successfully.
