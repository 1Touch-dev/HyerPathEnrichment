#!/bin/bash
# Rebuild and restart workers with the photo cache fix

cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend

echo "Building worker image with new code..."
docker compose --env-file .env.production \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.prod.yml \
  -f docker/docker-compose.tier1.yml \
  -f docker/docker-compose.multilogin.yml \
  -f docker/docker-compose.tier-workers.yml \
  build worker

echo ""
echo "Restarting worker containers..."
docker compose --env-file .env.production \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.prod.yml \
  -f docker/docker-compose.tier1.yml \
  -f docker/docker-compose.multilogin.yml \
  -f docker/docker-compose.tier-workers.yml \
  up -d --force-recreate worker-tier1 worker-tier234

echo ""
echo "Checking worker status..."
docker compose --env-file .env.production \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.prod.yml \
  -f docker/docker-compose.tier1.yml \
  -f docker/docker-compose.multilogin.yml \
  -f docker/docker-compose.tier-workers.yml \
  ps worker-tier1 worker-tier234

echo ""
echo "Done! Workers rebuilt with photo cache fix."
