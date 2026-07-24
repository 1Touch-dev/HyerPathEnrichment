from pathlib import Path
path = Path(r"G:/ThunderMarketingCorp/HyerEnrichment/.worktrees/sa4-setup/docs/SETUP_VERIFICATION.md")
text = path.read_text(encoding="utf-8")
addition = """

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
"""
if "SA4 re-run command log" not in text:
    path.write_text(text.rstrip() + addition + "\n", encoding="utf-8")
    print("updated")
else:
    print("already has sa4 section")
