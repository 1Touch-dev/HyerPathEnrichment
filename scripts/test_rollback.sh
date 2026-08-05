#!/bin/bash
set -e

echo "=== Foundation Week 1 Rollback Test ==="

# 1. Backup current state
echo "Step 1: Backing up current state..."
git rev-parse HEAD > /tmp/current_commit.txt
pg_dump -h localhost -U hyrepath hyrepath > /tmp/backup.sql

# 2. Perform rollback
echo "Step 2: Rolling back to agent-1-merged..."
git checkout master
git reset --hard agent-1-merged

# 3. Database rollback
echo "Step 3: Rolling back migrations..."
cd backend
alembic downgrade 008

# 4. Verify services
echo "Step 4: Verifying services..."
docker-compose restart api
sleep 5

# 5. Health check
echo "Step 5: Running health checks..."
curl -f http://localhost:8000/health || { echo "Health check failed"; exit 1; }

# 6. Verify document endpoints gone
echo "Step 6: Verifying document endpoints disabled..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/documents)
if [ "$STATUS" == "404" ]; then
  echo "✓ Document endpoints correctly disabled"
else
  echo "✗ Document endpoints still active"
  exit 1
fi

# 7. Restore original state
echo "Step 7: Restoring original state..."
git checkout $(cat /tmp/current_commit.txt)
alembic upgrade head
docker-compose restart api

echo "=== Rollback Test Complete ✓ ==="
