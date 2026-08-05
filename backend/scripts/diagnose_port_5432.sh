#!/usr/bin/env bash
# Diagnostic script to identify what's blocking port 5432
# Run this to collect evidence for Docker networking issues

echo "==================================================================="
echo "PORT 5432 DIAGNOSTIC REPORT"
echo "==================================================================="
echo ""

echo "[A] Checking for ALL Docker containers (including stopped/created)..."
echo "-------------------------------------------------------------------"
sudo docker ps -a
echo ""

echo "[B] Checking for postgres-specific containers..."
echo "-------------------------------------------------------------------"
sudo docker ps -a | grep postgres
echo ""

echo "[C] Checking Docker port bindings on all containers..."
echo "-------------------------------------------------------------------"
sudo docker ps --format "table {{.Names}}\t{{.Ports}}"
echo ""

echo "[D] Checking for processes using port 5432..."
echo "-------------------------------------------------------------------"
sudo ss -tlnp | grep 5432 || echo "No processes found on port 5432"
echo ""

echo "[E] Checking Docker networks..."
echo "-------------------------------------------------------------------"
sudo docker network ls
echo ""

echo "[F] Inspecting postgres container (if exists)..."
echo "-------------------------------------------------------------------"
sudo docker inspect docker-postgres-1 2>/dev/null | grep -A 10 "HostPort" || echo "No postgres container to inspect"
echo ""

echo "[G] Checking Docker bridge network details..."
echo "-------------------------------------------------------------------"
sudo docker network inspect docker_default 2>/dev/null | grep -A 5 "Containers" || echo "docker_default network not found"
echo ""

echo "==================================================================="
echo "DIAGNOSTIC COMPLETE"
echo "==================================================================="
