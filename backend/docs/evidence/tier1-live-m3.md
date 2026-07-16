# Evidence: Tier 1 live proof (Task 13 / M3)

**Branch:** `feat/tier1-live-windows-m3`  
**Date (UTC):** 2026-07-16  
**Runner:** `backend/scripts/verify_tier1_live.py` (Windows native, no Docker)

## Environment

| Component | Status |
|-----------|--------|
| Redis (Windows service) | **PASS** — `PONG` |
| Python 3.13 + deps | **PASS** |
| `tier1_canary_set.json` | **PASS** — 20 public profiles (gitignored) |
| MLX cloud API sign-in | **PASS** — 2 profiles in folder |
| MLX local launcher `:45001` | **BLOCKED** — HTTP 000; start Multilogin X desktop app |
| R2 credentials in `.env` | **PASS** — `R2_ACCOUNT_ID` set |
| `ENABLE_TIER1=true` + `APP_ENV=staging` | **PASS** (runtime env) |

## Commands run

```powershell
cd g:\ThunderMarketingCorp\HyerEnrichment\backend
$env:ENABLE_TIER1='true'; $env:APP_ENV='staging'
python scripts/verify_tier1_live.py --skip-live --json   # shape + prereqs
python -m app.workers.rq_worker                          # background worker
python scripts/verify_tier1_live.py --limit 3 --json     # live subset
```

## Results

| Step | Status | Exit | Notes |
|------|--------|------|-------|
| Shape tests (`test_sync_skips_tier1_photo`, `test_execute_job_runs_tier1_on_worker_path`) | **PASS** | 0 | After tier2 username fix in test payload |
| Prerequisites audit | **PASS** | 0 | MLX creds + selenium present |
| MLX `--connect-test` | **FAIL** | 1 | Launcher unreachable → Selenium port never opens |
| Isolation scrape | **FAIL** | 1 | Same launcher dependency |
| API canary (`e2e_tier1_canary.py --limit 3`) | **FAIL** | 1 | Jobs `completed` but `dossier.photo` empty (no MLX browser) |
| R2 upload proof | **NOT RUN** | — | Blocked until scrape succeeds |

## Artifacts

- `backend/.e2e-results/verify-tier1-live.json`
- `backend/.e2e-results/tier1-api-canary.json` — 3/3 FAIL (no photo; MLX launcher down)

## Pass criteria (remaining)

1. Start **Multilogin X** on Windows; `curl.exe -sk https://127.0.0.1:45001/api/v2/` → non-000.
2. Re-run: `python scripts/verify_tier1_live.py --json`
3. Confirm `tier1-api-canary.json` → `summary.fail == 0` and `asset_url` uses `R2_PUBLIC_BASE_URL`.

## Operator command

```powershell
cd backend
$env:ENABLE_TIER1='true'; $env:APP_ENV='staging'
python scripts/verify_tier1_live.py --json
```
