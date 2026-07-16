# Evidence: Langfuse staging (Task 49)

**Overall status:** **BLOCKED** — Docker CLI not available on this runner (docker not in PATH).

**Branch:** eat/langfuse-staging-49  
**Date (UTC):** 2026-07-16  
**Runner:** ackend/scripts/e2e_langfuse.sh

## Deliverables

- [ackend/scripts/e2e_langfuse.sh](../../scripts/e2e_langfuse.sh)

## Commands (when Docker is available)

```bash
# backend/.env: LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
bash backend/scripts/e2e_langfuse.sh
```

## Results (this host)

| Step | Status | Notes |
|------|--------|-------|
| e2e_langfuse.sh present | **PASS** | On branch |
| Docker / compose | **BLOCKED** | docker version failed: command not found |
| Langfuse UI :3000 | **NOT RUN** | Requires observability profile |
| 	race() smoke | **NOT RUN** | Requires compose stack |

## Pass criteria

- e2e_langfuse.sh exit 0
- langfuse-report.json under .e2e-results/
- Langfuse UI reachable on localhost:3000 after smoke 	race() call

## Unblock

Install/start Docker (or run on Linux CI with Docker), re-run the script, update this file to **PASS** or **FAIL** with logs.