#!/bin/sh
set -eu
TOKEN="${METRICS_TOKEN:-${API_TOKEN:-}}"
printf '%s' "$TOKEN" > /tmp/metrics_token
chmod 600 /tmp/metrics_token
exec /bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --storage.tsdb.retention.time=15d \
  --web.enable-lifecycle
