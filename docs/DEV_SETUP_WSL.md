# Dev Setup — WSL2 + Windows + Multilogin (Tier 1)

This document covers the one-time WSL2 configuration and the correct dev topology for running
Tier 1 (LinkedIn photo) locally on a Windows machine with Multilogin installed.

**When to read this:** You are on Windows/WSL2, `ENABLE_TIER1=true`, and either (a) Docker-published
ports (`localhost:6379`, `localhost:8000`) are not reachable from WSL, or (b) the RQ worker
cannot connect to Multilogin's Selenium debug port.

**Production (bare Linux / EC2):** see `backend/scripts/start_production.sh --with-linux-mlx`
and [`docs/adr/0008-tier1-linux-host-network.md`](adr/0008-tier1-linux-host-network.md).

---

## Problem 1 — `localhost` Docker ports not reachable in WSL

**Root cause:** WSL2's kernel does not auto-load `ip_tables`, so Docker Engine's iptables-based
port-forwarding silently fails. `localhost:6379`, `localhost:5432`, `localhost:8000` inside WSL
never reach the containers' published ports.

**Fix (one-time):** enable `systemd` in WSL so the kernel loads cleanly at boot and Docker can
run as a proper systemd service.

### Steps

1. Inside WSL, edit (or create) `/etc/wsl.conf`:

   ```ini
   [boot]
   systemd=true
   ```

2. From a PowerShell terminal, shut down WSL:

   ```powershell
   wsl --shutdown
   ```

3. Reopen WSL. Enable and start Docker as a systemd service:

   ```bash
   sudo systemctl enable docker
   sudo systemctl start docker
   ```

4. Verify iptables loaded:

   ```bash
   sudo iptables -L
   # should print a rule table, not an error
   ```

5. Start the Docker services and smoke-test:

   ```bash
   cd backend/docker
   docker compose -f docker-compose.yml up -d redis
   redis-cli -h localhost -p 6379 ping
   # PONG
   ```

After this step `localhost:6379` (Redis), `localhost:5432` (Postgres), and `localhost:8000` (API)
all work normally from WSL.

---

## Problem 2 — RQ worker cannot reach Multilogin's ChromeDriver port from Docker

**Root cause (architectural):** Multilogin binds the per-profile Selenium debug port to
`127.0.0.1` only — inside the Windows host's network namespace. A Docker bridge-networked
container has its own network namespace and has no route to that loopback regardless of hostname
mapping or bridge-IP tricks. This is OS-level isolation; it cannot be fixed by config.

**Decision:** see [`docs/adr/0008-tier1-linux-host-network.md`](adr/0008-tier1-linux-host-network.md)
for the full rationale. The short version: on Windows/WSL2 the worker must run **natively in WSL**
(not in Docker) so it shares the same `127.0.0.1` view as the Windows host where `mlxapp` runs.

---

## Dev topology (after both fixes)

```
Windows host
└── mlxapp (Multilogin daemon)
    ├── launcher API  → 127.0.0.1:45001
    └── Selenium port → 127.0.0.1:<DYNAMIC>   (loopback-only, not reachable from Docker)

WSL2 VM
├── RQ worker  (native Python process)         ← must be here for Tier 1
│   ├── reaches mlxapp via WSL↔Windows loopback  (MULTILOGIN_SELENIUM_HOST=http://127.0.0.1)
│   └── reaches Docker services via localhost    (after systemd fix)
│
└── Docker Engine
    ├── redis:6379
    ├── postgres:5432
    ├── api:8000
    ├── social-analyzer:9005
    ├── google-maps-scraper:8080
    └── email-verifier:8080
```

The API container does not need Tier 1 access (`ENABLE_TIER1=false` on the API is correct;
Tier 1 runs only on the worker).

---

## Running the stack

### 1. Start Docker services

```bash
cd backend/docker
docker compose -f docker-compose.yml up -d \
    redis postgres api \
    social-analyzer google-maps-scraper email-verifier
```

### 2. Start the RQ worker natively in WSL

With `backend/.env` already containing `MULTILOGIN_SELENIUM_HOST=http://127.0.0.1`:

```bash
cd /path/to/HyerEnrichment/backend
python -m app.workers.rq_worker
```

Or explicitly, if overriding env vars:

```bash
REDIS_URL=redis://localhost:6379/0 \
DATABASE_URL=sqlite+aiosqlite:///./hyrepath.db \
ENABLE_TIER1=true \
BROWSER_MODE=multilogin \
MULTILOGIN_SELENIUM_HOST=http://127.0.0.1 \
python -m app.workers.rq_worker
```

### 3. Verify

```bash
# API health
curl http://localhost:8000/health

# Submit a Tier 1 job (replace YOUR_TOKEN and LINKEDIN_URL)
curl -X POST http://localhost:8000/api/enrich \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"linkedin_url": "LINKEDIN_URL", "requested_tiers": [1]}'
```

---

## What NOT to do

| Approach | Why it fails |
|---|---|
| Hardcode WSL bridge IP (`172.26.x.x`) in `MULTILOGIN_SELENIUM_HOST` | IP changes on every WSL reset; the Selenium debug port is still loopback-only on Windows and unreachable from WSL |
| Run the RQ worker in Docker with `extra_hosts: host.docker.internal` | Reaches the Windows launcher API (port 45001) but not the dynamically-assigned Selenium debug port, which is bound to `127.0.0.1` only |
| TCP proxy for ChromeDriver ports | The debug port is dynamically assigned per `start_profile` response; setting up a forward before `connect_selenium` is called is fragile and unmaintainable (rejected in ADR 0008) |

---

## Production path (Linux / EC2)

On a bare Linux server use the supported tier-worker topology with `network_mode: host` only for
`worker-tier1` and `multilogin`. Those two containers share the host's loopback, so `127.0.0.1`
is the same socket for both while the bridge-network `worker` still consumes the non-tier queues
(including `audio_cleanup`). In that supported Linux path, `worker-tier1` reaches Postgres via
`127.0.0.1:5433` and Redis via `127.0.0.1:6379`, while the bridge-network services continue using
Docker DNS (`postgres:5432`, `redis:6379`):

```bash
bash backend/scripts/start_production.sh --with-linux-mlx
```

See [`backend/docker/docker-compose.multilogin.yml`](../backend/docker/docker-compose.multilogin.yml)
and [`docs/adr/0008-tier1-linux-host-network.md`](adr/0008-tier1-linux-host-network.md).
