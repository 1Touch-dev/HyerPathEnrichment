#!/usr/bin/env bash
# Deep diagnostic for persistent port 5432 issue
# Tests hypotheses: Docker daemon state, Windows services, iptables, WSL forwarding

echo "=========================================================================="
echo "DEEP DIAGNOSTIC: Port 5432 Persistence Issue"
echo "=========================================================================="
echo ""

echo "[Hypothesis F] Checking Docker daemon iptables/NAT rules..."
echo "----------------------------------------------------------------------"
sudo iptables -t nat -L -n | grep 5432 || echo "No iptables NAT rules for 5432"
echo ""

echo "[Hypothesis G] Checking WSL port forwarding (netsh from Windows)..."
echo "----------------------------------------------------------------------"
netsh.exe interface portproxy show all | grep 5432 || echo "No WSL port proxy for 5432"
echo ""

echo "[Hypothesis H] Checking Windows PostgreSQL services..."
echo "----------------------------------------------------------------------"
powershell.exe -Command "Get-Service | Where-Object {$_.Name -like '*postgres*'}" || echo "No Windows postgres services"
echo ""

echo "[Hypothesis I] Checking Docker daemon status and restart time..."
echo "----------------------------------------------------------------------"
sudo systemctl status docker 2>/dev/null || service docker status 2>/dev/null || echo "Cannot check docker service status (not systemd)"
echo ""
ps aux | grep dockerd | grep -v grep || echo "Docker daemon process info unavailable"
echo ""

echo "[Hypothesis J] Checking what happens during postgres container creation..."
echo "----------------------------------------------------------------------"
echo "Testing: Can we manually start postgres container?"
echo "Attempting: sudo docker run -d -p 127.0.0.1:5432:5432 --name test-postgres postgres:16-alpine"
sudo docker run -d -p 127.0.0.1:5432:5432 --name test-postgres postgres:16-alpine 2>&1 || echo "Manual postgres start FAILED"
echo ""
echo "If succeeded, cleaning up test container..."
sudo docker stop test-postgres 2>/dev/null && sudo docker rm test-postgres 2>/dev/null
echo ""

echo "[Additional] Checking if anything is ACTUALLY listening on 5432..."
echo "----------------------------------------------------------------------"
sudo ss -tlnp | grep 5432 || echo "Nothing listening on 5432"
sudo lsof -i :5432 2>/dev/null || echo "lsof: Nothing on 5432"
echo ""

echo "[Additional] Checking Docker daemon logs for port binding errors..."
echo "----------------------------------------------------------------------"
sudo journalctl -u docker -n 50 --no-pager 2>/dev/null | grep -i "5432\|bind\|address" || echo "No docker logs available (not systemd)"
echo ""

echo "=========================================================================="
echo "DIAGNOSTIC COMPLETE - Analyze results above"
echo "=========================================================================="
