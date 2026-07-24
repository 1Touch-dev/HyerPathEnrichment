#!/usr/bin/env bash
set -euo pipefail
unset DOCKER_HOST

echo "== podman info =="
podman info --format '{{.Host.RemoteSocket.Path}}' 2>&1 | head -5 || true
podman ps -a --format '{{.Names}}\t{{.Status}}' 2>&1 | head -20 || true

NAME=hyrepath-pg-test
if podman ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "removing existing $NAME"
  podman rm -f "$NAME" || true
fi

echo "== starting postgres via podman =="
podman run -d --name "$NAME" \
  -e POSTGRES_USER=hyrepath \
  -e POSTGRES_PASSWORD=hyrepath \
  -e POSTGRES_DB=hyrepath \
  -p 5432:5432 \
  docker.io/library/postgres:16

echo "== wait for ready =="
for i in $(seq 1 30); do
  if podman exec "$NAME" pg_isready -U hyrepath -d hyrepath >/dev/null 2>&1; then
    echo "postgres ready after ${i}s"
    podman exec "$NAME" pg_isready -U hyrepath -d hyrepath
    exit 0
  fi
  sleep 1
done
echo "postgres did not become ready"
podman logs "$NAME" | tail -40
exit 1
