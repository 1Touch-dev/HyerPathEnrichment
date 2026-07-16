 Evidence: Scrapoxy staging (Task 62)

**Branch:** `feat/scrapoxy-staging-62`  
**Date (UTC):** 2026-07-16  
**Runner:** `backend/scripts/e2e_scrapoxy.sh`  
**Overall status:** **BLOCKED** (Docker unavailable on proof host)

## Deliverables

- [`backend/docker/docker-compose.staging.yml`](../../docker/docker-compose.staging.yml) — Scrapoxy ports + healthcheck
- [`backend/scripts/e2e_scrapoxy.sh`](../../scripts/e2e_scrapoxy.sh) — staging proof script
- [`backend/docs/env.staging.example`](../../env.staging.example) — `PROXY_MODE=scrapoxy` template

## Commands

```bash
# Set in backend/.env:
# PROXY_MODE=scrapoxy
# SCRAPOXY_URL=http://scrapoxy:8888

bash backend/scripts/e2e_scrapoxy.sh
pytest tests/test_enrichers.py -k scrapoxy -v
```

## Results (Sub-agent C — Windows host)

| Step | Status | Notes |
|------|--------|-------|
| Docker CLI / daemon | **BLOCKED** | `docker` not recognized in PATH; e2e compose not executed |
| `test_proxy_provider_scrapoxy_builds_authenticated_url` | **PASS** | `python -m pytest tests/test_enrichers.py -k scrapoxy -v` (host, no Docker) |
| Scrapoxy container up | **NOT RUN** | Requires Docker |
| `ProxyProvider.get()` in worker | **NOT RUN** | Requires `docker compose` + staging overlay |
| Live sherlock via proxy | **OPTIONAL** | EMPTY OK without Scrapoxy proxy fleet in commander |

## Pass criteria (full PASS requires Docker)

- `e2e_scrapoxy.sh` exit 0
- `scrapoxy-report.json` written under `.e2e-results/`
- `ProxyProvider` returns non-empty URL when `PROXY_MODE=scrapoxy` inside worker container

## Unblock

Install/start Docker Desktop (or Podman with compose compatibility), then from repo root:

```bash
bash backend/scripts/e2e_scrapoxy.sh
```

Re-run on CI or a Linux staging host with Docker to move status from **BLOCKED** to **PASS**.

## Note

Scrapoxy commander must have an active **proxy project** for egress. Wiring proof (this script) is separate from fleet-backed enrichment volume.
