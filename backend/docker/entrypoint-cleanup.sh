#!/bin/bash
set -e

echo "=== Cleanup Worker Starting ==="
echo "Running job cleanup maintenance tasks..."

exec "$@"
