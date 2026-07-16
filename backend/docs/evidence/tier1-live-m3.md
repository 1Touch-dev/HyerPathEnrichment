# Evidence: Tier 1 live proof (Task 13 / M3)

**Branch:** `feat/tier1-live-windows-m3`  
**Date (UTC):** 2026-07-16  
**Runner:** `backend/scripts/verify_tier1_live.py` (Windows native, no Docker for Tier 1)

## Environment

| Component | Status |
|-----------|--------|
| Redis (Windows service `Redis`) | **PASS** — `redis-cli ping` → `PONG` |
| API (`uvicorn` :8000) | **PASS** — `curl.exe -s http://127.0.0.1:8000/health` → HTTP 200 |
| RQ worker (`ENABLE_TIER1=true`, `APP_ENV=staging`) | **PASS** — background `python -m app.workers.rq_worker` |
| `tier1_canary_set.json` (gitignored) | **PASS** — 20 public profiles, no placeholders |
| MLX local launcher `127.0.0.1:45001` | **BLOCKED** — TCP closed; Multilogin X desktop not listening |
| R2 / MLX cloud prereqs (`probe_tier1.py --prereqs`) | **PASS** — exit 0 |

## Git / branch setup

```powershell
cd g:\ThunderMarketingCorp\HyerEnrichment
git fetch origin
git checkout main
git pull origin main
git checkout feat/tier1-live-windows-m3
```

| Step | Status |
|------|--------|
| `git fetch` / `main` pull | **PASS** (transient `index.lock` may require manual delete) |
| Branch `feat/tier1-live-windows-m3` | **PASS** |

## Commands run (this session)

```powershell
cd g:\ThunderMarketingCorp\HyerEnrichment\backend
$env:ENABLE_TIER1 = 'true'
$env:APP_ENV = 'staging'

Start-Process python -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000' -WorkingDirectory (Get-Location)
Start-Process python -ArgumentList '-m','app.workers.rq_worker' -WorkingDirectory (Get-Location)

python scripts/verify_tier1_live.py --json
python scripts/verify_tier1_live.py --skip-live --json
```

## Results

| Step | Status | Exit | Notes |
|------|--------|------|-------|
| Shape tests | **PASS** | 0 | pytest via runner |
| Prerequisites audit | **PASS** | 0 | `probe_tier1.py --prereqs` |
| Canary file check | **PASS** | 0 | gitignored local file |
| MLX `--connect-test` | **FAIL** | 1 | `httpx.ConnectError` |
| Isolation scrape | **FAIL** | 1 | launcher dependency |
| `probe_tier1_canary.py` | **FAIL** | 1 | connect error |
| API canary `e2e_tier1_canary.py` | **FAIL** | 1 | see `tier1-api-canary.json` |
| `run_canary_score.py --tier tier1` | **FAIL** | 1 | connect error |
| **Overall live run** | **BLOCKED** | **1** | unblock `:45001` |
| **`--skip-live`** | **PASS** | **0** | shape + prereqs |

## Artifacts (local, not committed)

| Path | Description |
|------|-------------|
| `backend/.e2e-results/verify-tier1-live.json` | Last invocation (skip-live exit 0 after live run) |
| `backend/.e2e-results/verify-tier1-live-run.log` | Full live `--json` stdout (**exit 1**, `mode: live`, `2026-07-16T09:33:56Z`) |
| `backend/.e2e-results/tier1-api-canary.json` | API canary from live run |
| `backend/.e2e-results/uvicorn-m3.err.log` | API stderr |
| `backend/.e2e-results/rq-worker-m3.err.log` | Worker stderr |

## Pass criteria (remaining)

1. Start **Multilogin X**; confirm `127.0.0.1:45001` accepts connections.
2. Re-run `python scripts/verify_tier1_live.py --json` with API + worker up.
3. Confirm `tier1-api-canary.json` → `summary.fail == 0` and R2 public URLs.

```powershell
cd backend; $env:ENABLE_TIER1='true'; $env:APP_ENV='staging'; python scripts/verify_tier1_live.py --json
```
