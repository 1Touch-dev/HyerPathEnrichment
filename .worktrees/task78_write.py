from pathlib import Path
import json

report = json.loads(Path(r"G:/ThunderMarketingCorp/HyerEnrichment/backend/.e2e-results/full-path-report.json").read_text(encoding="utf-8"))
evidence = Path(r"G:/ThunderMarketingCorp/HyerEnrichment/backend/docs/e2e-evidence/2026-07-16-full-path-ci.md")
stage_rows = "\n".join(
    f"| {s['name']} | {s['script']} | {s['ok']} | {s['exit_code']} | {s['duration_seconds']} |"
    for s in report["stages"]
)
body = f"""# Full-path E2E evidence (CI mode)

Developer Guide **Task 78** / DEVPLAN gap **78**.

## Run

- **Date (UTC):** 2026-07-16
- **Harness:** `backend/scripts/e2e_full_path_runner.py --ci`
- **Make target:** `make e2e-full-path` (repo root)
- **Host:** Windows 10; **Docker:** WSL2 (native Windows `docker` not on PATH)
- **Command:**

```bash
wsl bash -lc 'cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend && export DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 && python3 scripts/e2e_full_path_runner.py --ci'
```

## Aggregate report

Generated at `{report['generated_at']}` (mode `{report['mode']}`).

| Metric | Value |
|--------|-------|
| passed | {report['passed']} |
| failed | {report['failed']} |
| skipped | {report['skipped']} |

### Stages

| Stage | Script | OK | Exit | Duration (s) |
|-------|--------|----|------|--------------|
{stage_rows}

## Path covered

1. **compose_test** — API health, async enqueue/poll (queue + worker), opt-out suppression/purge, Postgres durability after worker restart.
2. **fake_sidecars** — Compose fake sidecar stack, tier integration probes, async tier-4 job with fixture business data.

## Raw JSON

```json
{json.dumps(report, indent=2)}
```
"""
evidence.write_text(body + "\n", encoding="utf-8")

devplan = Path(r"G:/ThunderMarketingCorp/HyerEnrichment/docs/DEVPLAN.md")
text = devplan.read_text(encoding="utf-8")
text = text.replace("- [ ] **Full-path E2E (gap 78)**", "- [x] **Full-path E2E (gap 78)**")
old_row = "| **78** | Full request"
for line in text.splitlines():
    if line.startswith("| **78** |"):
        text = text.replace(line, "| **78** | Full request→…→storage E2E | `e2e_full_path_runner.py` + evidence | Phase 5 - **closed** |")
        break
devplan.write_text(text, encoding="utf-8")
print("ok")
