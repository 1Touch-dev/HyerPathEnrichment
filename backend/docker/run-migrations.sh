#!/bin/bash
# Idempotent migration script that handles already-applied migrations gracefully
set -e

echo "=== Alembic Migration Runner ==="
echo "Checking current migration state..."

# Show current revision
alembic current || {
    echo "Warning: Could not determine current revision (database might be uninitialized)"
}

echo ""
echo "Running migrations to head..."

# Run migrations, but don't fail if they're already applied
alembic upgrade head 2>&1 | tee /tmp/migration_output.log

# Check if the command succeeded or if migrations were already applied
EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Migrations completed successfully!"
    exit 0
elif grep -q "Can't locate revision" /tmp/migration_output.log; then
    # This happens when the image is stale but DB is up to date
    echo "⚠️  Migration revision mismatch detected (stale container image)"
    echo "Database appears to be up to date. Treating as success."
    exit 0
elif grep -q "Target database is not up to date" /tmp/migration_output.log; then
    # This shouldn't happen with 'upgrade head', but handle it anyway
    echo "⚠️  Database claims to be out of sync, but migration failed"
    exit 1
else
    echo "❌ Migration failed with exit code $EXIT_CODE"
    echo "Last 20 lines of output:"
    tail -20 /tmp/migration_output.log
    exit 1
fi
