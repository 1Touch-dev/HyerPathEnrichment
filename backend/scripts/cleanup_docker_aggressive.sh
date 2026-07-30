#!/usr/bin/env bash
# Complete cleanup script to forcefully remove all containers and free port 5432
# This is more aggressive than docker compose down

set -euo pipefail

echo "==================================================================="
echo "AGGRESSIVE DOCKER CLEANUP FOR PORT 5432 ISSUE"
echo "==================================================================="
echo ""

echo "[1] Stopping ALL running containers..."
RUNNING=$(sudo docker ps -q)
if [ -n "$RUNNING" ]; then
  sudo docker stop $RUNNING
  echo "✓ Stopped containers"
else
  echo "ℹ No running containers"
fi
echo ""

echo "[2] Removing ALL containers (including stopped/created)..."
ALL_CONTAINERS=$(sudo docker ps -a -q)
if [ -n "$ALL_CONTAINERS" ]; then
  sudo docker rm -f $ALL_CONTAINERS
  echo "✓ Removed all containers"
else
  echo "ℹ No containers to remove"
fi
echo ""

echo "[3] Pruning Docker networks..."
sudo docker network prune -f
echo "✓ Networks pruned"
echo ""

echo "[4] Verifying port 5432 is free..."
PORT_CHECK=$(sudo ss -tlnp | grep 5432 || echo "")
if [ -z "$PORT_CHECK" ]; then
  echo "✓ Port 5432 is FREE"
else
  echo "⚠ WARNING: Port 5432 still in use:"
  echo "$PORT_CHECK"
fi
echo ""

echo "==================================================================="
echo "CLEANUP COMPLETE - Ready to retry startup"
echo "==================================================================="
