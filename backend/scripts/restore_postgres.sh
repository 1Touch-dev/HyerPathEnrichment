#!/bin/bash
# Restore Postgres database from backup
# Usage: ./restore_postgres.sh <path-to-backup-file.sql.gz>

set -euo pipefail

# Configuration
CONTAINER_NAME=${POSTGRES_CONTAINER:-docker-postgres-1}
DB_USER=${POSTGRES_USER:-hyrepath}
DB_NAME=${POSTGRES_DB:-hyrepath}
COMPOSE_DIR=${COMPOSE_DIR:-backend/docker}

# Check arguments
if [ $# -ne 1 ]; then
  echo "Usage: $0 <backup-file.sql.gz>" >&2
  echo "Example: $0 /backups/postgres/hyrepath-20260728-020001.sql.gz" >&2
  exit 1
fi

BACKUP_FILE="$1"

# Validate backup file
if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
  echo "ERROR: Backup file is corrupted or not a valid gzip: $BACKUP_FILE" >&2
  exit 1
fi

echo "=========================================="
echo "Postgres Restore"
echo "=========================================="
echo "Backup file: $BACKUP_FILE"
echo "Database: $DB_NAME"
echo "Container: $CONTAINER_NAME"
echo "=========================================="
echo ""

# Confirm restore
read -p "This will OVERWRITE the current database. Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Restore aborted by user."
  exit 0
fi

# Stop services
echo ""
echo "Step 1/5: Stopping API and worker services..."
cd "$COMPOSE_DIR"
docker compose stop api worker worker-tier1 worker-tier234 || true
echo "✓ Services stopped"

# Drop and recreate database
echo ""
echo "Step 2/5: Dropping and recreating database..."
docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres <<EOF
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = '$DB_NAME' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME OWNER $DB_USER;
EOF
echo "✓ Database recreated"

# Restore from backup
echo ""
echo "Step 3/5: Restoring from backup (this may take several minutes)..."
if gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" > /dev/null; then
  echo "✓ Restore complete"
else
  echo "ERROR: Restore failed" >&2
  echo "Check Postgres logs: docker logs $CONTAINER_NAME"
  exit 1
fi

# Run migrations
echo ""
echo "Step 4/5: Running Alembic migrations..."
docker compose up -d migrate
echo "Waiting for migrations to complete..."
sleep 5
if docker compose logs migrate | grep -q "Migration complete"; then
  echo "✓ Migrations complete"
else
  echo "WARNING: Migration logs unclear, check manually:"
  docker compose logs migrate
fi

# Start services
echo ""
echo "Step 5/5: Starting services..."
docker compose up -d api worker
sleep 3
echo "✓ Services started"

# Verify
echo ""
echo "=========================================="
echo "Restore Complete"
echo "=========================================="
echo ""
echo "Verification steps:"
echo "  1. Check health: curl http://localhost:8000/health"
echo "  2. Check job count: docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -c 'SELECT COUNT(*) FROM jobs;'"
echo "  3. Check recent jobs: docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -c 'SELECT id, status, created_at FROM jobs ORDER BY created_at DESC LIMIT 5;'"
echo "  4. Monitor logs: docker compose logs -f api worker"
echo ""
echo "If verification fails, review logs and consider restoring from an older backup."
echo ""
