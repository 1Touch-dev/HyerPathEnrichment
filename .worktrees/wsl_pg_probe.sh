#!/usr/bin/env bash
set -uo pipefail
echo "== docker group =="
getent group docker || true
echo "== members of docker =="
grep '^docker:' /etc/group || true
echo "== can we read sock =="
ls -la /var/run/docker.sock
echo "== try runuser/sudo without password for docker group add? =="
sudo -n true 2>&1 || echo "no passwordless sudo"
echo "== postgres/podman packages =="
command -v psql || true
command -v podman || true
command -v postgres || true
dpkg -l | grep -E 'postgresql|podman|docker' 2>/dev/null | head -30 || true
echo "== listening 5432 in wsl =="
ss -ltn | grep 5432 || netstat -ltn 2>/dev/null | grep 5432 || true
echo "== docker context =="
docker context ls 2>&1 | head -20 || true
env | grep -i docker || true
env | grep -i podman || true
