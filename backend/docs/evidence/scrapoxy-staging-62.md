# Evidence: Scrapoxy staging (Task 62)

**Branch:** `feat/scrapoxy-staging-62`  
**Date (UTC):** 2026-07-16

## Status: **BLOCKED** (Docker unavailable)

## Deliverables in repo

- `backend/docker/docker-compose.staging.yml` — Scrapoxy ports 8888/8890, `PROXY_MODE` passthrough
- `backend/scripts/e2e_scrapoxy.sh` — staging proof script

## Operator steps (when Docker available)

```powershell
cd backend\docker
docker compose -f docker-compose.yml -f docker-compose.staging.yml --profile paid up -d scrapoxy api worker redis postgres
cd ..\..
# Set PROXY_MODE=scrapoxy, SCRAPOXY_URL=http://localhost:8888 in backend/.env; restart containers
bash backend/scripts/e2e_scrapoxy.sh
```

## Pass criteria

- `ProxyProvider().get()` returns non-null inside worker
- `backend/.e2e-results/scrapoxy-report.json` → `exit_code: 0`
