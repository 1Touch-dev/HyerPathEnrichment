# Evidence: Tier 2–4 live E2E (M4–M10)

**Branch:** `feat/tier234-live-e2e`  
**Date (UTC):** 2026-07-16  
**Runner:** `backend/scripts/verify_tier234_live.py`

## Environment

| Component | Status |
|-----------|--------|
| Docker | **BLOCKED** — `docker` not in PATH; Docker Desktop not installed |
| WSL | **BLOCKED** — `Wsl/Service/E_UNEXPECTED` |
| Python E2E scripts | **READY** — `e2e_tier2.py`, `e2e_tier3.py`, `e2e_realworld_strict.py` |

## Commands run

```powershell
cd g:\ThunderMarketingCorp\HyerEnrichment\backend
python scripts/verify_tier234_live.py --skip-live --json
# Live (not run):
# python scripts/verify_tier234_live.py --json
```

## Results

| Step | Status | Notes |
|------|--------|-------|
| Unit tests (shape, tier2/3 merge, enrichers) | **PASS** | 51 passed |
| `probe_sidecars.sh` | **BLOCKED** | Docker required |
| `e2e_tier2.py` | **BLOCKED** | Needs compose sidecars |
| `e2e_tier3.py` | **BLOCKED** | Needs compose sidecars |
| `e2e_realworld_strict.py` | **BLOCKED** | Needs compose sidecars |
| `run_canary_score.py --tier tier234` | **BLOCKED** | Live probes need sidecars |
| `strict-report.json` `failed: 0` | **PENDING** | |

## Artifacts

- `backend/.e2e-results/verify-tier234-live.json` — skip-live **exit_code: 0**

## Operator checklist

1. Install **Docker Desktop**; confirm `docker info` works in PowerShell.
2. `cd backend/docker; docker compose --env-file ..\.env up -d api worker redis postgres social-analyzer google-maps-scraper email-verifier`
3. `cd backend; python scripts/verify_tier234_live.py --json`
4. Confirm `strict-report.json` → `"failed": 0`.
