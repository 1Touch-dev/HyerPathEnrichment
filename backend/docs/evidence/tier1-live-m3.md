# Evidence: Tier 1 live proof (Task 13 / M3)

**Branch:** `feat/prove-tier1-live-m3`  
**Date (UTC):** 2026-07-16  
**Runner:** `backend/scripts/verify_tier1_live.py`

## Commands run

```powershell
cd g:\ThunderMarketingCorp\HyerEnrichment\backend
python scripts/verify_tier1_live.py --skip-live --json
python scripts/probe_tier1.py --prereqs
python scripts/probe_tier1.py --connect-test   # blocked — see below
```

## Results

| Step | Status | Notes |
|------|--------|-------|
| Shape tests (`sync_skips_tier1`, `execute_job_runs_tier1`) | **PASS** | 2 passed |
| Prerequisites audit | **PASS** | MLX email/folder/bot creds present; `ENABLE_TIER1=false` in local `.env` (expected until tier1 compose override) |
| `tier1_canary_set.json` | **BLOCKED** | File not filled — copy `docs/tier1_canary_set.example.json` → `docs/tier1_canary_set.json` with 20 permitted public profiles (gitignored) |
| MLX launcher (`:45001`) | **BLOCKED** | `curl.exe -sk https://127.0.0.1:45001/api/v2/` → HTTP 000; start Multilogin X on Windows before connect-test |
| MLX API sign-in | **PARTIAL** | `probe_tier1.py --connect-test` signed in and acquired profile; Selenium stop failed when launcher unreachable |
| Isolation canary | **NOT RUN** | Requires filled canary + MLX launcher |
| API canary (`e2e_tier1_canary.py`) | **NOT RUN** | Requires Docker worker with `docker-compose.tier1.yml` + MLX |
| R2 upload proof | **NOT RUN** | Set `APP_ENV=staging` + `R2_*` on worker; confirm `asset_url` uses `R2_PUBLIC_BASE_URL` |

## Operator checklist to reach M3 sign-off

1. Start **Multilogin X** on Windows; verify `curl.exe -sk https://127.0.0.1:45001/api/v2/` returns non-000 (often 404).
2. Fill **`docs/tier1_canary_set.json`** (never commit).
3. Set **`APP_ENV=staging`** and **`R2_*`** in `backend/.env` or `WORKER_ENV_FILE`.
4. WSL2: `export MULTILOGIN_HOST_IP=$(ip route show default | awk '{print $3}')`.
5. Bring up stack:
   ```bash
   cd backend/docker
   docker compose -f docker-compose.yml -f docker-compose.tier1.yml up -d --build api worker redis postgres
   ```
6. Run full proof:
   ```bash
   cd backend
   python scripts/verify_tier1_live.py --json
   ```

## Pass criteria (unchanged)

- `verify-tier1-live.json` → `exit_code: 0`
- `e2e_tier1_canary.py` report → ≥14/20 `PASS` on `expect_photo=true` rows
- Photo `asset_url` on R2 public base, not local `.asset-cache/`
- `run_canary_score.py --tier tier1` → status **RAN**, not SKIP

## Artifacts

- `backend/.e2e-results/verify-tier1-live.json` (skip-live run recorded)
