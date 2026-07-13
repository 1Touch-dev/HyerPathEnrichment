# Tier 2–4 testing checklist

Enrichers **fail silently**: the pipeline can return `status: "completed"` with no error while individual sources return `{}`. Use **`dossier.sources`** in API responses to see which enrichers contributed data.

---

## Layer 0 — Shape tests (mocked, fast)

```bash
cd backend
pytest tests/test_pipeline_shape.py -v
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
| Email Verify | 3 | `mailchecker` (core dep, disposable blocklist); `dnspython` (`pip install .[enrichers]`); optional Reacher for SMTP |
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

Strict contract + API path:

```bash
cd backend
python scripts/e2e_realworld_strict.py
# or: bash scripts/e2e_realworld_strict.sh
```

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

Stable test subjects: `torvalds`, company `github` / `Microsoft`, email `noreply@github.com`, job `"software engineer remote"`, business `"coffee shop San Francisco"`.

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
  -d '{"username":"torvalds","email":"torvalds@example.com","company":"github","requested_tiers":["tier3"]}' | python -m json.tool
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
| Social Analyzer | ☐ | handles |
| GitRecon | ☐ | github + handles |
| theHarvester | ☐ | emails |
| Email Sleuth | ☐ | emails |
| Email Verify | ☐ | verified_emails |
| CrossLinked | ☐ | coworkers |
| JobSpy | ☐ | jobs |
| Google Maps | ☐ | business |

---

## Env vars (serious Tier 2–4 run)

```env
SOCIAL_ANALYZER_URL=http://social-analyzer:9005    # Docker network
GMAPS_SCRAPER_URL=http://google-maps-scraper:8080
GITRECON_SCRIPT=/path/to/gitrecon.py
GITHUB_TOKEN=ghp_...                               # optional
EMAIL_VERIFY_LEVEL=basic
```

Local dev (not Docker): point URLs to `localhost:9005` / `localhost:8080`. Install extras:

```bash
cd backend && pip install -e ".[enrichers]"
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

Use **WSL2 + Docker Desktop** for bash scripts (`e2e_realworld_strict.sh`, `probe_sidecars.sh`):

```powershell
wsl -d Ubuntu-22.04 -u root bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/e2e_realworld_strict.sh
```

---

## Expected gaps in default Docker worker

| Enricher | Likely status | Why |
|----------|---------------|-----|
| Email Discover | Partial OK | Pattern fallback without `email-sleuth` |
| Email Verify | Partial OK | MX if `dnspython` installed |
| Social Analyzer / Local Business | Depends | Sidecar up + correct API contract |
| Sherlock, Maigret, TheHarvester, CrossLinked, GitRecon, JobSpy | Often EMPTY | CLIs / jobspy not in `Dockerfile.worker` by default |

Validate CLI enrichers locally (tools on host) with Layer 3 while Docker worker image is still minimal.
