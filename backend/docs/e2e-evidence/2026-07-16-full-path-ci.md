# Full-path E2E CI evidence — 2026-07-16

## Command

```bash
make e2e-full-path
# equivalent:
cd backend && python scripts/e2e_full_path_runner.py --ci
```

## Environment

- OS: Windows 10 (WSL2)
- Runner: `backend/scripts/e2e_full_path_runner.py` (WSL bash path fix applied)
- Docker: WSL socket permission denied (`/var/run/docker.sock`)

## Report summary

Source: `backend/.e2e-results/full-path-report.json` (gitignored)

| Field | Value |
|-------|-------|
| `generated_at` | 2026-07-16T09:18:56Z |
| `mode` | ci |
| `passed` | 0 |
| `failed` | 2 |
| `skipped` | 0 |

## Stages

| Stage | Script | OK | Exit | Duration (s) | Notes |
|-------|--------|----|------|--------------|-------|
| compose_test | e2e_compose_test.sh | false | 1 | 88.44 | Docker daemon permission denied in WSL |
| fake_sidecars | e2e_fake_sidecars.sh | false | 1 | 93.94 | Docker daemon permission denied in WSL |

## Verdict

Harness and Makefile target are in place; **green CI run blocked** on this host until Docker Desktop WSL integration grants socket access. Re-run after `docker info` succeeds inside WSL.
