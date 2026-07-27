#!/bin/bash
set -e

echo "=== Worker Startup Coordinator ==="

# Extract worker number from hostname (e.g., "worker-tier234-3" -> "3")
WORKER_INDEX=$(echo $HOSTNAME | grep -oP '\d+$' || echo "1")

# Get delay from environment (default 10 seconds)
DELAY_PER_WORKER=${WORKER_STARTUP_DELAY:-10}

# Calculate this worker's delay
WAIT_TIME=$((DELAY_PER_WORKER * (WORKER_INDEX - 1)))

if [ $WAIT_TIME -gt 0 ]; then
    echo "Worker #$WORKER_INDEX: Waiting ${WAIT_TIME} seconds before starting..."
    echo "  (Staggered startup to avoid proxy rate limits)"
    sleep $WAIT_TIME
fi

echo "Worker #$WORKER_INDEX: Starting RQ worker now!"
echo "  Queue: ${WORKER_TARGET_QUEUE}"
echo "  Hostname: ${HOSTNAME}"

# Execute the original worker command
# This passes control to the Python RQ worker
exec "$@"
