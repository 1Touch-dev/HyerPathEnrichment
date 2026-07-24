## Problem

The base `docker-compose.yml` did not publish Redis port 6379 to the host. This caused `Connection refused` when native WSL workers tried to connect via `localhost:6379`, even after the systemd + iptables fix was applied.

Docker services (API, containerized worker if used) reach Redis via `redis:6379` on the bridge network and were unaffected. But native WSL workers — required for Tier 1 due to ChromeDriver Host-header security — could not connect.

## Fix

Added `ports: ["6379:6379"]` to the `redis` service in `docker-compose.yml`.

After this change + systemd enabled in WSL:

```bash
redis-cli -h localhost -p 6379 ping  # returns PONG
.venv/bin/rq worker enrichment       # connects successfully
```

## Impact

- Dev WSL setup: native workers now connect to Redis without manual bridge IP lookups
- Docker services: unchanged, still use `redis:6379`
- Production: unchanged, `docker-compose.prod.yml` already removes all port publishing

## Testing

```bash
wsl -u axiz -e bash -c "redis-cli -h localhost -p 6379 ping"
# Expected: PONG
```
