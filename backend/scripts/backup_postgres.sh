#!/bin/bash
# Automated Postgres backup for Hyrepath Enrichment
# Run via cron: 0 2 * * * /opt/hyrepath/HyerPathEnrichment/backend/scripts/backup_postgres.sh

set -euo pipefail

# Configuration
BACKUP_DIR=${BACKUP_DIR:-/backups/postgres}
RETENTION_DAYS=${RETENTION_DAYS:-30}
CONTAINER_NAME=${POSTGRES_CONTAINER:-docker-postgres-1}
DB_USER=${POSTGRES_USER:-hyrepath}
DB_NAME=${POSTGRES_DB:-hyrepath}

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Generate timestamp
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/hyrepath-$DATE.sql.gz"

# Log start
echo "$(date): Starting Postgres backup to $BACKUP_FILE"

# Check if Postgres container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "$(date): ERROR: Postgres container $CONTAINER_NAME is not running" >&2
  exit 1
fi

# Perform backup
if docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" -d "$DB_NAME" | gzip > "$BACKUP_FILE"; then
  echo "$(date): Backup complete: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
else
  echo "$(date): ERROR: Backup failed" >&2
  rm -f "$BACKUP_FILE"
  exit 1
fi

# Verify backup integrity
if gzip -t "$BACKUP_FILE" 2>/dev/null; then
  echo "$(date): Backup integrity verified"
else
  echo "$(date): ERROR: Backup file is corrupted" >&2
  exit 1
fi

# Rotate old backups
echo "$(date): Rotating backups older than $RETENTION_DAYS days"
DELETED_COUNT=$(find "$BACKUP_DIR" -name "hyrepath-*.sql.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
echo "$(date): Deleted $DELETED_COUNT old backup(s)"

# Report success
echo "$(date): Backup workflow complete"
exit 0
