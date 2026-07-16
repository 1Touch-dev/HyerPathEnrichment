# Fresh-setup verification

**Date:** 2026-07-16  
**Branch:** `chore/fresh-setup-verify-m16`  
**Base SHA:** `f41e41f213c709dac8fd98221fdb90b3932378d8` (origin/main)  
**Result:** PASS

## Environment

| Item | Value |
|------|--------|
| Host OS | Windows 10 (build 26200) |
| Runtime | WSL2 Ubuntu (rootless Podman via `DOCKER_HOST=unix:///run/user/1000/podman/podman.sock`) |
| Make | GNU Make 4.4.1 (WSL) |
| Python (setup/smoke) | 3.14.4 via `backend/.venv` |
| Docker CLI | Podman 5.7.0 (rootless) |
| Native Windows Docker Desktop | Not on PATH |
| Native Windows GNU Make | Not on PATH |

Notes:

- Documented path `make setup` → `make up` → `make smoke` run from WSL against this worktree.
- Makefile creates `backend/.venv` (PEP 668) and installs `requests` for smoke.
- `make up` uses `DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0` for Podman compatibility.

## Commands run

```bash
export DOCKER_HOST=unix:///run/user/1000/podman/podman.sock
make setup
make up
# wait until curl http://127.0.0.1:8000/health → {"status":"ok",...}
make smoke
```

## Results

| Step | Result | Evidence |
|------|--------|----------|
| `make setup` | PASS | Created `backend/.env`, `backend/.venv`; installed editable backend + `requests` |
| `make up` | PASS | Free stack up: api, worker, redis, postgres, social-analyzer, google-maps-scraper |
| Wait healthy | PASS | `GET /health` → `{"status":"ok","service":"Hyrepath Enrichment Backend"}` |
| `make smoke` | PASS (exit 0) | See log excerpt below |

### `make smoke` log excerpt

```text
PASS  /health
PASS  unauth /enrich/sync → 401
PASS  /enrich/sync → completed
smoke ok
```

## DEVPLAN updates

Phase 1 gaps **1+79** (Makefile), **77** (smoke beyond health), and **84** (fresh-setup verification) marked complete when merged to `main`.

## Not done

- Did **not** merge to `main` (review via PR).

## SA4 re-run command log (2026-07-16)

Executed via WSL from `/mnt/g/ThunderMarketingCorp/HyerEnrichment` (native Windows: no `make`/`docker` on PATH).

```bash
export DOCKER_HOST=unix:///run/user/1000/podman/podman.sock
export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0
make setup          # exit 0 (logs: /tmp/m16-setup.log)
make up             # exit 0 (logs: /tmp/m16-up.log)
curl -s http://127.0.0.1:8000/health
make smoke          # exit 1 on first attempt (enrich/sync read timeout during stack recycle)
make smoke          # exit 0 on retry after health stable
```

| Step | Exit code | Notes |
|------|-----------|--------|
| `make setup` | 0 | `backend/.env` present; editable install + `requests` in `backend/.venv` (Python 3.14.4) |
| `make up` | 0 | Recreated/started api, worker, redis, postgres, social-analyzer, google-maps-scraper |
| `GET /health` (pre-smoke) | 0 | `{"status":"ok","service":"Hyrepath Enrichment Backend"}` |
| `make smoke` (1st) | 1 | `FAIL /enrich/sync unreachable: Read timed out` — other checks passed |
| `make smoke` (retry) | 0 | Full pass (excerpt below) |

### Retry `make smoke` log excerpt

```text
{"status":"ok","service":"Hyrepath Enrichment Backend"}
PASS  /health
PASS  unauth /enrich/sync → 401
PASS  /enrich/sync → completed
smoke ok
```

