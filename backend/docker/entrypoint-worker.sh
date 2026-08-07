#!/bin/bash
set -e

echo "=== Worker Startup Coordinator ==="

# Get delay from environment (default 10 seconds)
DELAY_PER_WORKER=${WORKER_STARTUP_DELAY:-10}

# Skip staggered startup if delay is 0 or not set
if [ "$DELAY_PER_WORKER" = "0" ] || [ -z "$DELAY_PER_WORKER" ]; then
    echo "Worker: Staggered startup disabled (WORKER_STARTUP_DELAY=${DELAY_PER_WORKER})"
else
    # Extract worker replica number from Docker Compose hostname
    # Docker Compose scaled services use format: service_name-replica_number-container_id
    # Examples: "worker-tier234-1", "worker-tier234-2-abc123def"
    # We want the replica number (the first number after the last hyphen before any hash)

    # Try to extract replica number from scaled service format
    WORKER_INDEX=$(echo "$HOSTNAME" | grep -oP '(?<=-)\d+(?=[-]|$)' | head -1 || echo "1")

    # Safety cap: if extracted number is unreasonably large (>100), default to 1
    if [ "$WORKER_INDEX" -gt 100 ]; then
        echo "Warning: Extracted worker index $WORKER_INDEX seems invalid, using 1"
        WORKER_INDEX=1
    fi

    # Calculate this worker's delay
    WAIT_TIME=$((DELAY_PER_WORKER * (WORKER_INDEX - 1)))

    if [ $WAIT_TIME -gt 0 ]; then
        echo "Worker #$WORKER_INDEX: Waiting ${WAIT_TIME} seconds before starting..."
        echo "  (Staggered startup to avoid proxy rate limits)"
        sleep $WAIT_TIME
    fi
fi

echo "Worker #$WORKER_INDEX: Starting RQ worker now!"
echo "  Queue: ${WORKER_TARGET_QUEUE}"
echo "  Hostname: ${HOSTNAME}"

# Execute the original worker command
# This passes control to the Python RQ worker
exec "$@"
