#!/usr/bin/env bash
set -euo pipefail
unset DOCKER_HOST
export DOCKER_HOST=unix:///var/run/docker.sock

echo "== groups =="
id
echo "== try sg docker =="
if sg docker -c 'docker ps --format "{{.Names}}\t{{.Status}}"' 2>/tmp/docker_sg.err; then
  echo "sg docker OK"
else
  echo "sg docker FAILED:"
  cat /tmp/docker_sg.err || true
fi

echo "== docker.exe paths =="
ls "/mnt/c/Program Files/Docker/Docker/resources/bin/" 2>/dev/null | head -20 || true
ls /mnt/c/Users/AZIZ/AppData/Local/Programs/Docker 2>/dev/null | head -10 || true

echo "== try docker.exe =="
if command -v docker.exe >/dev/null 2>&1; then
  docker.exe ps --format '{{.Names}}\t{{.Status}}' 2>&1 | head -20
elif [ -x "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe" ]; then
  "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe" ps --format '{{.Names}}\t{{.Status}}' 2>&1 | head -20
else
  echo "no docker.exe found"
fi
