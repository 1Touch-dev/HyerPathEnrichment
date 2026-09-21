#!/bin/bash
# Rebuild and restart workers with the photo cache fix on the supported Linux MLX path

cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend

echo "Building supported worker images with new code..."
docker compose --env-file .env.production \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.prod.yml \
  -f docker/docker-compose.foundation.yml \
  -f docker/docker-compose.tier-workers.yml \
  -f docker/docker-compose.multilogin.yml \
  build worker worker-email worker-cleanup worker-job-matching

echo ""
echo "Restarting worker containers..."
docker compose --env-file .env.production \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.prod.yml \
  -f docker/docker-compose.foundation.yml \
  -f docker/docker-compose.tier-workers.yml \
  -f docker/docker-compose.multilogin.yml \
  up -d --force-recreate worker worker-email worker-cleanup worker-job-matching worker-tier1 worker-tier234 multilogin

echo ""
echo "Checking worker status..."
docker compose --env-file .env.production \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.prod.yml \
  -f docker/docker-compose.foundation.yml \
  -f docker/docker-compose.tier-workers.yml \
  -f docker/docker-compose.multilogin.yml \
  ps worker worker-email worker-cleanup worker-job-matching worker-tier1 worker-tier234 multilogin

echo ""
echo "Done! Supported Linux MLX workers rebuilt with photo cache fix."
