# Tier 2–4 testing checklist

Enrichers **fail silently**: the pipeline can return `status: "completed"` with no error while individual sources return `{}`. Use **`dossier.sources`** in API responses to see which enrichers contributed data.

---

## Tier 2 full E2E (recommended first)

One-shot free-path + litellm harness for Sherlock / Maigret / Social Analyzer:

```bash
bash backend/scripts/e2e_tier2.sh
```

Windows (WSL):

```powershell
wsl -d Ubuntu-22.04 -u root bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/e2e_tier2.sh
```

**Stage A (free):** rebuilds `api` + `worker` with `sherlock`/`maigret` on PATH, brings up `social-analyzer`, asserts isolation probes, `/enrich/sync` and async `/enrich` for `requested_tiers:["tier2"]`. Report: `backend/.e2e-results/tier2-report.json`.

**Stage B (litellm):** requires `OPENAI_API_KEY` or `GEMINI_API_KEY` in `backend/.env`. Starts `--profile llm` and runs live `_disambiguate_handles` via the proxy.

### Scrapoxy (optional, not gated)

Default is `PROXY_MODE=none` (direct; ban risk at volume). CrossLinked uses **Yahoo** search by default (`CROSSLINKED_SEARCH_ENGINES=yahoo`) via the maintained fork in Docker images; upstream v0.3.0 Bing/Google are blocked in containers. Optional Scrapoxy:

```bash
cd backend/docker
# Start scrapoxy behind paid profile, then:
# PROXY_MODE=scrapoxy SCRAPOXY_URL=http://scrapoxy:8888 docker compose --profile paid up -d
# Confirm Sherlock/Maigret CLI invocations include --proxy (see ProxyProvider + enricher args).
```

---

## Layer 0 — Shape tests (mocked, fast)

```bash
cd backend
pytest tests/test_pipeline_shape.py tests/test_tier2_merge.py tests/test_enrichers.py -v
```

Proves merge/scoring — **not** that real CLIs or sidecars work.

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
| GitRecon | 3 | `GITRECON_SCRIPT` → `gitrecon.py` |
| TheHarvester | 3 | `theHarvester` on PATH |
| Email Discover | 3 | `email-sleuth` (optional; pattern fallback always returns something) |
| Email Verify | 3 | `mailchecker` (core dep); `dnspython` (`pip install .[enrichers]`); `EMAIL_VERIFIER_URL` (AfterShip sidecar); optional Reacher when `EMAIL_VERIFY_LEVEL=smtp` |
| CrossLinked | 3 | `crosslinked` on PATH |
| JobSpy | 4 | `pip install .[enrichers]` |
| Local Business | 4 | Sidecar + `GMAPS_SCRAPER_URL` |

---

## Layer 2 — Sidecar health

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

**GMaps compose note:** service builds via [`Dockerfile.google-maps-scraper`](../docker/Dockerfile.google-maps-scraper) (upstream binary + Playwright 1.57.0 driver assembled from npm/nodejs.org). Do **not** mount a volume over `/opt` — that shadows `/opt/node` and `/opt/package`. Hub `:latest` alone still 404s on the retired azureedge CDN.

Strict contract + API path:

```bash
cd backend
python scripts/e2e_realworld_strict.py
# or: bash scripts/e2e_realworld_strict.sh
```

### Free-sidecar smoke (2026-07-13)

| Check | Result |
|-------|--------|
| Worker → SA `:9005/get_settings` | PASS (HTTP 200) |
| Worker → GMaps `:8080/api/docs` | PASS (HTTP 200) |
| Sync `tier2`+`tier4` (`torvalds` + `coffee shop San Francisco`) | PASS — `sources`: Social Analyzer + Google Maps Scraper; 3 handles; business `Hey Neighbor Cafe` |
| `e2e_realworld_strict` GMaps create/poll/download | PASS (`status=ok`, csv ~397KB) |
| `e2e_realworld_strict` SA settings/analyze | PASS |
| Unrelated FAILs | `GITRECON_SCRIPT` unset; `gmaps_legacy_search_rejected` (GET `/search` returns 200, probe expects 4xx) |

---

## Layer 3 — Enricher isolation

```bash
cd backend
python scripts/probe_enrichers.py
python scripts/probe_enrichers.py --only sherlock,maigret --json
```

| Output | Meaning |
|--------|---------|
| `SKIP` | Required request field missing |
| `EMPTY {}` | Tool missing, timeout, or no results |
| `OK` | Enricher returned data — inspect keys |

Stable test subjects: `torvalds` / `satyanadella` (GitHub), company `Microsoft`, email `noreply@github.com`, job `"software engineer remote"`, business `"coffee shop San Francisco"`.

---

## Layer 4 — Tier-by-tier API (`/enrich/sync`)

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
| Sherlock | ☐ | handles |
| Maigret | ☐ | handles |
| Social Analyzer | ☑ | handles (3 for `torvalds`, 2026-07-13 smoke) |
| GitRecon | ☐ | github + handles |
| theHarvester | ☐ | emails |
| Email Sleuth | ☐ | emails |
| Email Verify | ☐ | verified_emails |
| CrossLinked | ☐ | coworkers |
| JobSpy | ☐ | jobs |
| Google Maps | ☑ | business (`Hey Neighbor Cafe`, 2026-07-13 smoke) |

---

## Env vars (serious Tier 2–4 run)

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

Stage B (optional): `RUN_TIER3_SMTP=1 bash backend/scripts/e2e_tier3.sh` — also starts Reacher (`--profile paid`) when `EMAIL_VERIFY_LEVEL=smtp`.

Unit tests:

```bash
cd backend
pytest tests/test_tier3_merge.py tests/test_enrichers.py
```

---

## Recommended order

1. `docker compose up` (api + worker + sidecars)
2. `python scripts/e2e_realworld_strict.py` → read `.e2e-results/strict-report.json`
3. For each FAIL → `python scripts/probe_enrichers.py --only <name>`
4. Fix prerequisites (CLI, env, sidecar)
5. Re-run tier curl commands above
6. Test async: `POST /enrich` + poll `GET /enrich/{id}`

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

Use **WSL2 + Docker Desktop** for bash scripts (`e2e_tier2.sh`, `e2e_realworld_strict.sh`, `probe_sidecars.sh`):

```powershell
wsl -d Ubuntu-22.04 -u root bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/e2e_tier2.sh
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
