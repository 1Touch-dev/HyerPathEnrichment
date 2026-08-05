# Restart Tier1 Worker with Increased Timeout

The browser timeout has been increased from 45s to 90s to handle slow LinkedIn page loads.

## Restart Command

Run this in your WSL terminal:

```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.multilogin.yml \
  -f docker-compose.tier-workers.yml \
  --env-file ../.env.production \
  restart worker-tier1
```

## Test Again

After restart, test the 3 profiles:

```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment
bash test-tier1-only.sh
```

The increased timeout should allow LinkedIn pages to load successfully.
