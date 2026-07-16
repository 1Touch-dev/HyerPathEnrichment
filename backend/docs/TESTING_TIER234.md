# Tier 2â€“4 testing checklist

Enrichers **fail silently**: the pipeline can return `status: "completed"` with no error while individual sources return `{}`. Use **`dossier.sources`** in API responses to see which enrichers contributed data.

---

## Full-path runner (CI + live glue)

One command chains the existing shell harnesses and writes an aggregate report.

| Mode | Stages |
|------|--------|
| `--ci` (default) | `e2e_compose_test.sh` → `e2e_fake_sidecars.sh` |
| `--live` | `probe_sidecars.sh` → `e2e_tier2.sh` → `e2e_tier3.sh` → `e2e_realworld_strict.sh` |
| `--all` | `--ci` then `--live` |

```bash
bash backend/scripts/e2e_full_path.sh              # CI path (default)
bash backend/scripts/e2e_full_path.sh --live
bash backend/scripts/e2e_full_path.sh --all
```

Windows (PowerShell; uses WSL/bash when native bash is missing):

```powershell
cd g:\ThunderMarketingCorp\HyerEnrichment\backend
python scripts/e2e_full_path_runner.py --ci
```

Report: `backend/.e2e-results/full-path-report.json` (non-zero exit if any stage fails).

Env:

- `E2E_SKIP_COMPOSE=1` — skip `e2e_compose_test.sh` when the compose stack is already up.
- `E2E_KEEP_STACK=1` — forwarded to child scripts that tear down compose on exit.

---

## Script responsibilities

| Script | Validates | Services |
|--------|-----------|----------|
| `e2e_full_path.sh` / `e2e_full_path_runner.py` | Orchestrates CI and/or live stages above | varies by mode |
| `probe_sidecars.sh` | Ephemeral sidecar smoke (HTTP reachability + job API) | GMaps, Social Analyzer, email-verifier |
| `e2e_tier2.sh` | Tier 2 pipeline (CLIs + SA sidecar + sync/async API) | Sherlock, Maigret, Social Analyzer |
| `e2e_tier3.sh` | Tier 3 pipeline (CLIs + email-verifier + sync/async API) | GitRecon, theHarvester, Email Sleuth, Email Verify, CrossLinked |
| `e2e_realworld_strict.sh` | Cross-tier strict contract + enricher live probes | GMaps, Social Analyzer, GitRecon + API sync |

**Probe vs enricher:** `probe_sidecars.sh` checks that sidecars respond on the HTTP paths enrichers use. Enrichers in `app/enrichers/` parse responses into dossier fragments. A probe pass does not guarantee enrichment — run tier or strict E2E for that.

**GitRecon is not a sidecar** — it is a subprocess CLI (`GITRECON_SCRIPT=/opt/gitrecon/gitrecon.py`) validated by `e2e_tier3.sh` and `e2e_realworld_strict.sh`, not `probe_sidecars.sh`.

---

## Tier 2 full E2E (recommended first)

One-shot free-path + litellm harness for Sherlock / Maigret / Social Analyzer:

```bash
bash backend/scripts/e2e_tier2.sh
```

Windows (WSL):

```powershell
wsl -d Ubuntu -u root bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/e2e_tier2.sh
```

**Stage A (free):** rebuilds `api` + `worker` with `sherlock`/`maigret` on PATH, brings up `social-analyzer`, asserts isolation probes, `/enrich/sync` and async `/enrich` for `requested_tiers:["tier2"]`. Report: `backend/.e2e-results/tier2-report.json`.

**Stage B (litellm):** optional — requires `OPENAI_API_KEY` or `GEMINI_API_KEY` in `backend/.env`. Without keys, Stage A still runs and Stage B is skipped with a WARN.

### Scrapoxy (optional, not gated)

Default is `PROXY_MODE=none` (direct; ban risk at volume). CrossLinked uses **Yahoo** search by default (`CROSSLINKED_SEARCH_ENGINES=yahoo`) via the maintained fork in Docker images; upstream v0.3.0 Bing/Google are blocked in containers.

**Staging proof (Task 62):**

```bash
# backend/.env: PROXY_MODE=scrapoxy SCRAPOXY_URL=http://scrapoxy:8888
cd backend/docker
docker compose -f docker-compose.yml -f docker-compose.staging.yml --profile paid up -d scrapoxy api worker
bash backend/scripts/e2e_scrapoxy.sh
```

Confirms `ProxyProvider` returns the scrapoxy URL inside the worker. Live enricher data still requires proxy fleet configured in the Scrapoxy commander GUI. See `backend/docs/evidence/scrapoxy-staging-62.md`.

---

## Layer 0 â€” Shape tests (mocked, fast)

```bash
cd backend
pytest tests/test_pipeline_shape.py tests/test_tier2_merge.py tests/test_enrichers.py -v
```

Proves merge/scoring â€” **not** that real CLIs or sidecars work.

---

## Layer 1.5 — Fake sidecar integration (CI-safe)

Deterministic HTTP integration through Docker **without** building AGPL/Playwright/Go sidecars. Proves `api`/`worker` reachability, sidecar HTTP contracts, enricher parsing, and async tier4 business data.

```bash
cd backend
pytest tests/test_fake_sidecar_server.py -v
bash backend/scripts/e2e_fake_sidecars.sh
# Windows/WSL (if .sh has CRLF issues):
python backend/scripts/e2e_fake_sidecars_runner.py
```

Compose override:

```bash
cd backend/docker
docker compose -f docker-compose.yml -f docker-compose.fake-sidecars.yml --profile paid up --build -d \
  api worker redis postgres social-analyzer google-maps-scraper email-verifier reacher
```

Report: `backend/.e2e-results/fake-sidecars-report.json`.

**Scope:** sidecar HTTP wiring + parsing only. Live Sherlock/Maigret/gitrecon OSINT and real Google/SMTP remain on `e2e_tier2.sh`, `e2e_tier3.sh`, and `e2e_realworld_strict.sh` (manual/nightly).

---

## Layer 1 — Prerequisites audit

```bash
cd backend
python scripts/probe_enrichers.py --prereqs
```

Or inside the worker container:

```bash
cd backend/docker
docker compose exec worker sh -c 'which sherlock maigret theHarvester crosslinked email-sleuth 2>/dev/null; python -c "import jobspy" 2>&1'
```

| Enricher | Tier | Needs on worker |
|----------|------|-----------------|
| Sherlock | 2 | `sherlock` on PATH |
| Maigret | 2 | `maigret` on PATH |
| Social Analyzer | 2 | Sidecar + `SOCIAL_ANALYZER_URL` |
| GitRecon | 3 | `GITRECON_SCRIPT` â†’ `gitrecon.py` |
| TheHarvester | 3 | `theHarvester` on PATH |
| Email Discover | 3 | `email-sleuth` (optional; pattern fallback always returns something) |
| Email Verify | 3 | `mailchecker` (core dep); `dnspython` (`pip install .[enrichers]`); `EMAIL_VERIFIER_URL` (AfterShip sidecar); optional Reacher when `EMAIL_VERIFY_LEVEL=smtp` |
| CrossLinked | 3 | `crosslinked` on PATH |
| JobSpy | 4 | `pip install .[enrichers]` |
| Local Business | 4 | Sidecar + `GMAPS_SCRAPER_URL` |

---

## Layer 2 â€” Sidecar health

```bash
cd backend/docker
docker compose up --build -d api worker redis postgres social-analyzer google-maps-scraper
bash backend/scripts/probe_sidecars.sh   # WSL/Linux
```

Manual probes:

```bash
curl http://localhost:9005/get_settings
curl http://localhost:8080/api/docs
```

**GMaps compose note:** service builds via [`Dockerfile.google-maps-scraper`](../docker/Dockerfile.google-maps-scraper) (upstream binary + Playwright 1.57.0 driver assembled from npm/nodejs.org). `probe_sidecars.sh` uses the same Dockerfile. Do **not** mount a volume over `/opt` — that shadows `/opt/node` and `/opt/package`. Hub `:latest` alone still 404s on the retired azureedge CDN.

Strict contract + API path (pipes Python probe into api container — `scripts/` is dockerignored):

```bash
bash backend/scripts/e2e_realworld_strict.sh
```

Local-only (host has gitrecon + sidecars on localhost):

```bash
cd backend
python scripts/e2e_realworld_strict.py
```

### Free-sidecar smoke

**Contract expectations:**

| Check | Expected |
|-------|----------|
| `probe_sidecars.sh` GMaps job create/status | POST `/api/v1/jobs`, GET `/api/v1/jobs/{id}` |
| `probe_sidecars.sh` SA settings/analyze | GET `/get_settings`, POST `/analyze_string` |
| Legacy GET `/search` on GMaps/SA | May return 200 — **not used by enrichers** |
| `e2e_realworld_strict` GMaps create/poll/download | Job API + CSV download |
| `e2e_tier3` GitRecon | `GITRECON_SCRIPT=/opt/gitrecon/gitrecon.py` in api/worker images |

**Observed smoke (reference run):**

| Check | Result |
|-------|--------|
| Worker → SA `:9005/get_settings` | PASS (HTTP 200) |
| Worker → GMaps `:8080/api/docs` | PASS (HTTP 200) |
| Sync `tier2`+`tier4` (`torvalds` + `coffee shop San Francisco`) | PASS — `sources`: Social Analyzer + Google Maps Scraper; 3 handles; business `Hey Neighbor Cafe` |
| `e2e_realworld_strict` GMaps create/poll/download | PASS (`status=ok`, csv ~397KB) |
| `e2e_realworld_strict` SA settings/analyze | PASS |
| Unrelated FAILs | `GITRECON_SCRIPT` unset; `gmaps_legacy_search_rejected` (GET `/search` returns 200, probe expects 4xx) |

### Expected free-path contract behavior

| Check | Expectation |
|-------|-------------|
| GMaps enricher path | `POST /api/v1/jobs` → poll → `GET .../download` CSV (not `GET /search`) |
| SA enricher path | `GET /get_settings` + `POST /analyze_string` with profile candidates |
| GitRecon | Subprocess CLI via `GITRECON_SCRIPT=/opt/gitrecon/gitrecon.py` (not in `probe_sidecars.sh`) |
| Legacy `/search` | May return 200; enrichers do not use it — strict labels as unused |
| Evidence | `backend/.e2e-results/strict-report.json` should report `failed: 0` |

---

## Layer 3 â€” Enricher isolation

```bash
cd backend
python scripts/probe_enrichers.py
python scripts/probe_enrichers.py --only sherlock,maigret --json
```

| Output | Meaning |
|--------|---------|
| `SKIP` | Required request field missing |
| `EMPTY {}` | Tool missing, timeout, or no results |
| `OK` | Enricher returned data â€” inspect keys |

Stable test subjects: `torvalds` / `satyanadella` (GitHub), company `Microsoft`, email `noreply@github.com`, job `"software engineer remote"`, business `"coffee shop San Francisco"`.

---

## Layer 3.5 — 20-profile canary (run/score)

### Canary file schema (20 rows)

The committed example uses **public identifiers already exercised in this repo** (no random people's LinkedIn URLs). Copy to a local override only when you need custom rows:

```bash
cd backend
cp docs/tier234_canary_set.example.json docs/tier234_canary_set.json   # optional; gitignored
```

| Field | Required | Purpose |
|-------|----------|---------|
| `id` | yes | Stable row id for reports |
| `category` | yes | `technical`, `non-technical`, or `sparse` |
| `username` | no | OSINT handle (e.g. `torvalds`, `satyanadella`) |
| `email` | no | Public mailbox (e.g. `noreply@github.com`) |
| `company` | no | Company name (e.g. `Microsoft`) |
| `job_search` | no | JobSpy query string |
| `business` | no | GMaps query string |
| `enrichers` | yes | List of enricher slugs to probe for this row |

### Copy → fill → run

```bash
cd backend

# 1) Use the committed example as-is, or copy and edit locally
cp docs/tier234_canary_set.example.json docs/tier234_canary_set.json   # optional

# 2) Isolation probe + PASS/FAIL/SKIP scorecard
python scripts/probe_enrichers.py --canary docs/tier234_canary_set.example.json --json
# or with local override:
python scripts/probe_enrichers.py --canary docs/tier234_canary_set.json --json

# 3) Combined ops runner (copies example when local file missing)
python scripts/run_canary_score.py --tier tier234 --json
python scripts/run_canary_score.py --tier all --dry-run    # plan only
python scripts/run_canary_score.py --tier all --limit 3 --json
```

Reports: `backend/.e2e-results/tier234-canary.json`, `canary-run-score.json`.

**SKIP notes:** `JobSpy` auto-skips on native Windows unless `--include-jobspy`. `local_business` and `social_analyzer` return `EMPTY`/`SKIP` when sidecars are down — that is expected outside Docker.

Unit tests (no live CLIs): `pytest tests/test_probe_enrichers_canary.py tests/test_canary_sets.py -v`

---

## Layer 4 â€” Tier-by-tier API (`/enrich/sync`)

**Tier 2:**

```bash
curl -s -X POST http://localhost:8000/enrich/sync \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -d '{"username":"torvalds","requested_tiers":["tier2"]}' | python -m json.tool
```

**Tier 3:**

```bash
curl -s -X POST http://localhost:8000/enrich/sync \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -d '{"username":"torvalds","email":"torvalds@example.com","company":"Microsoft","requested_tiers":["tier3"]}' | python -m json.tool
```

**Tier 4:**

```bash
curl -s -X POST http://localhost:8000/enrich/sync \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -d '{"job_search":"software engineer remote","business":"coffee shop San Francisco","requested_tiers":["tier4"]}' | python -m json.tool
```

### Scorecard (fill after each run)

| Source | In `sources`? | Data returned? |
|--------|---------------|----------------|
| Sherlock | â˜ | handles |
| Maigret | â˜ | handles |
| Social Analyzer | â˜‘ | handles (3 for `torvalds`, 2026-07-13 smoke) |
| GitRecon | â˜ | github + handles |
| theHarvester | â˜ | emails |
| Email Sleuth | â˜ | emails |
| Email Verify | â˜ | verified_emails |
| CrossLinked | â˜ | coworkers |
| JobSpy | â˜ | jobs |
| Google Maps | â˜‘ | business (`Hey Neighbor Cafe`, 2026-07-13 smoke) |

---

## Env vars (serious Tier 2â€“4 run)

```env
SOCIAL_ANALYZER_URL=http://social-analyzer:9005    # Docker network
GMAPS_SCRAPER_URL=http://google-maps-scraper:8080
GITRECON_SCRIPT=/opt/gitrecon/gitrecon.py          # Docker worker/api default
EMAIL_VERIFIER_URL=http://email-verifier:8080      # AfterShip sidecar (basic mode)
EMAIL_VERIFY_LEVEL=basic                           # basic | smtp (Reacher)
EMAIL_VERIFY_MAX_PER_JOB=10
GITHUB_TOKEN=ghp_...                               # optional
```

Local dev (not Docker): point URLs to `localhost:9005` / `localhost:8080`. Install extras:

```bash
cd backend && pip install -e ".[enrichers]"
```

---

## Tier 3 full E2E

```bash
bash backend/scripts/e2e_tier3.sh
```

Stage A (default): api + worker + redis + postgres + **email-verifier** sidecar; asserts all five Tier 3 sources on sync + async enrich.

Stage B (optional): `RUN_TIER3_SMTP=1 bash backend/scripts/e2e_tier3.sh` â€” also starts Reacher (`--profile paid`) when `EMAIL_VERIFY_LEVEL=smtp`.

Unit tests:

```bash
cd backend
pytest tests/test_tier3_merge.py tests/test_enrichers.py
```

---

## Recommended order

**Quick CI (compose + fake sidecars):**

```bash
bash backend/scripts/e2e_full_path.sh --ci
# or: python backend/scripts/e2e_full_path_runner.py --ci
```

**Full manual / nightly (live sidecars + tiers):**

1. `docker compose up` (api + worker + sidecars)
2. `pytest tests/test_enrichers.py tests/test_pipeline_shape.py -v` (Layer 0 / shape + parser unit tests)
3. `bash backend/scripts/probe_sidecars.sh` (Layer 2 sidecar smoke — GMaps / SA / email-verifier)
4. `bash backend/scripts/e2e_tier2.sh` → `tier2-report.json` (Tier 2 free path)
5. `bash backend/scripts/e2e_tier3.sh` → `tier3-report.json` (Tier 3 free path; includes GitRecon)
6. `bash backend/scripts/e2e_realworld_strict.sh` → read `backend/.e2e-results/strict-report.json` (`failed: 0`) (or local `python scripts/e2e_realworld_strict.py`)
7. For each FAIL → `python scripts/probe_enrichers.py --only <name>` then fix prerequisites and re-run
8. Re-run tier curl commands above
9. Test async: `POST /enrich` + poll `GET /enrich/{id}`

Or run steps 3–6 in one shot: `bash backend/scripts/e2e_full_path.sh --live` (or `--all` after CI).

---

## Windows note

Use **PowerShell** for native paths:

```powershell
cd g:\ThunderMarketingCorp\HyerEnrichment\backend
python scripts/probe_enrichers.py
```

In **bash/WSL**, convert the drive letter:

```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend
python scripts/probe_enrichers.py
```

**JobSpy on native Windows:** `python-jobspy` loads numpy; some Windows Python 3.13 builds segfault at runtime. The probe script auto-skips JobSpy on Windows unless you pass `--include-jobspy` (runs in a subprocess so a crash won't kill the whole script). Prefer testing JobSpy inside Docker/WSL.

Use **WSL2 + Docker Desktop** for bash scripts. Default distro is `Ubuntu` (not necessarily `Ubuntu-22.04`):

```powershell
wsl -d Ubuntu -u root bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/e2e_tier2.sh
```

Ensure shell scripts use Unix line endings (LF). If you see `set: pipefail: invalid option name`, run:

```bash
sed -i 's/\r$//' backend/scripts/*.sh
```

---

## Expected gaps in default Docker worker

| Enricher | Likely status | Why |
|----------|---------------|-----|
| GitRecon / theHarvester / CrossLinked / Email Sleuth | OK after rebuild | Baked into `Dockerfile.worker` + `Dockerfile.api` |
| Email Verify (basic) | OK when sidecar up | `email-verifier` compose service + two-phase verify in `runner.py` |
| Email Verify (SMTP) | Opt-in | `EMAIL_VERIFY_LEVEL=smtp` + `docker compose --profile paid up reacher` |
| Social Analyzer / Local Business | Depends | Sidecar up + correct API contract |
| Sherlock, Maigret | OK after rebuild | Installed via `.[enrichers]` in worker/api images |
| JobSpy | Often EMPTY on Windows | Prefer Docker/WSL; see Windows note below |

Validate CLI enrichers locally with Layer 3 (`probe_enrichers.py`) when not using Docker.
