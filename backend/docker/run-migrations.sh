#!/bin/bash
# Idempotent migration script that handles already-applied migrations gracefully
set -e

echo "=== Alembic Migration Runner ==="
echo "Running migrations to head..."

# Run migrations, but don't fail if they're already applied.
#
# NOTE: `alembic current` used to run here first, purely as an informational
# log line (its result was never used for branching logic). On a genuinely
# fresh database that is a serious bug, not just a cosmetic ordering issue:
# `alembic current` still executes this repo's env.py (see
# `_widen_version_table_if_needed` in backend/alembic/env.py), which creates
# the (empty) `alembic_version` table with an explicit `connection.commit()`
# as a side effect. That first invocation's commit ends its transaction
# cleanly. But the *next* `alembic upgrade head` invocation then finds the
# table already exists at the target width, so `_widen_version_table_if_needed`
# takes its no-op branch — running only a `SELECT` and never calling
# `connection.commit()`. That `SELECT` auto-begins a transaction on the
# connection (SQLAlchemy 2.x autobegin), so when Alembic's own
# `context.begin_transaction()` subsequently finds the connection already
# "in a transaction", it nests the actual migration DDL inside a SAVEPOINT
# instead of a top-level transaction. `run_migrations_online()` never issues
# an explicit outer `connection.commit()`, so closing that connection rolls
# the whole thing back — releasing the savepoint is meaningless once the
# transaction that contains it is rolled back. Every migration silently
# no-ops (exit code 0, "successfully" logged) while the DB stays unmigrated.
# Reproduced directly: on a fresh DB, `alembic current` then `alembic upgrade
# head` back-to-back leaves only an empty `alembic_version` table behind.
#
# Fix: run `alembic current` only *after* `alembic upgrade head` has already
# succeeded, so it can never touch a not-yet-migrated fresh DB first and can
# never poison the upgrade's connection/transaction state.
alembic upgrade head 2>&1 | tee /tmp/migration_output.log

# Check if the command succeeded or if migrations were already applied
EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Migrations completed successfully!"
    echo ""
    echo "Current migration state:"
    alembic current || {
        echo "Warning: Could not determine current revision after a successful upgrade"
    }
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
