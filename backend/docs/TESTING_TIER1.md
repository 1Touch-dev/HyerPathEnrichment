# Tier 1 testing checklist

LinkedIn profile photo enrichment uses **Multilogin + Selenium on the worker only**.
`/enrich/sync` never runs Tier 1 even if `tier1` is in `requested_tiers`.

---

## Layer 0 — Shape tests (mocked, fast)

```bash
cd backend
pytest tests/test_pipeline_shape.py -v -k "sync_skips_tier1 or execute_job_runs_tier1"
```

Proves sync skips Tier 1 and the async worker path can merge a photo fragment.

---

## Layer 1 — Prerequisites audit

```bash
cd backend
python scripts/probe_tier1.py --prereqs
```

Inside the worker container:

```bash
cd backend/docker
docker compose exec worker python -c "import selenium; print('selenium OK')"
docker compose exec worker chromium --version
```

| Check | Needs |
|-------|--------|
| `ENABLE_TIER1` | `true` on **worker** only (API stays `false`) |
| `BROWSER_MODE` | `multilogin` in prod; `local` only for dev experiments |
| `MULTILOGIN_*` | Email, password (MD5 in code), folder id, launcher URL |
| `LINKEDIN_BOT_*` | Dummy LinkedIn account for Selenium login |
| `MULTILOGIN_SELENIUM_HOST` | `http://host.docker.internal` from Docker worker |
| `selenium` + Chromium | Installed in `Dockerfile.worker` via `.[enrichers]` |
| R2 (optional) | `R2_*` creds; unset writes to `backend/.asset-cache/` |

---

## Layer 2 — Multilogin connectivity

Multilogin launcher must be running on the host (not inside Docker).

```bash
cd backend
python scripts/probe_tier1.py --connect-test
python scripts/probe_tier1.py --scrape --linkedin-url https://www.linkedin.com/in/<slug>
```

From the worker container (host MLX must be reachable):

```bash
cd backend/docker
docker compose -f docker-compose.yml -f docker-compose.tier1.yml exec worker \
  python scripts/probe_tier1.py --prereqs
```

---

## Layer 3 — Docker worker (async path)

Build and start the stack (Tier 1 off by default):

```bash
cd backend/docker
docker compose up --build -d api worker redis postgres
```

Enable Tier 1 on the worker (recommended override file):

```bash
cd backend/docker
docker compose -f docker-compose.yml -f docker-compose.tier1.yml up -d --build worker
```

Or one-off env:

```bash
ENABLE_TIER1=true BROWSER_MODE=multilogin docker compose up -d worker
```

Worker reaches Multilogin on the host via `host.docker.internal` (`extra_hosts` in compose).
Failure screenshots land in the `tier1_artifacts` volume (`artifacts/tier1/` in the container).

Enqueue a job:

```bash
curl -s -X POST http://localhost:8000/enrich \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "linkedin_url": "https://www.linkedin.com/in/<slug>",
    "requested_tiers": ["tier1"]
  }'
```

Poll `GET /enrich/{job_id}` until `status` is `completed`; expect `dossier.photo.asset_url`.

Repeat the same `linkedin_url` with query variants — second job should hit **slug cache** (no new MLX profile start in worker logs).

---

## Layer 4 — Sync path guard

`/enrich/sync` must **not** return a photo when `tier1` is requested:

```bash
curl -s -X POST http://localhost:8000/enrich/sync \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "linkedin_url": "https://www.linkedin.com/in/<slug>",
    "requested_tiers": ["tier1", "tier2"]
  }'
```

Expect `dossier.photo` null/absent and no `linkedin-photo` in `dossier.sources`.

---

## Layer 5 — Prometheus metrics (optional)

When `prometheus_client` is installed, `GET /metrics` exposes Tier 1 counters:

| Metric | Meaning |
|--------|---------|
| `tier1_cache_hits_total` | Slug cache hits (skipped browser) |
| `tier1_cache_misses_total` | Cache misses (browser scrape attempted) |
| `tier1_scrape_total{outcome=...}` | Scrape results (`success`, `captcha`, etc.) |
| `tier1_upload_total{result=...}` | R2/local upload success or error |

```bash
curl -s http://localhost:8000/metrics | grep tier1_
```

---

## Confidence scores (locked)

| Extraction | Score |
|------------|-------|
| `og:image` | 0.84 |
| DOM fallback | 0.70 |

---

## Layer 6 — Canary QA (Phase 3.7)

Copy the example canary file and fill with ~20 real public profiles:

```bash
cp docs/tier1_canary_set.example.json docs/tier1_canary_set.json
# edit slugs/URLs — technical, non-technical, private
python scripts/probe_tier1_canary.py --file docs/tier1_canary_set.json --pool-status --json
```

| Column | Track |
|--------|--------|
| `slug` | Normalized `/in/{slug}` |
| `category` | `technical` / `non-technical` / `private` |
| `status` | `OK`, `CACHE_HIT`, `FAIL`, `SKIP` |
| `outcome` | `success`, `captcha`, `placeholder_image`, etc. |

### Rate limit tuning

| Env var | Default | Purpose |
|---------|---------|---------|
| `MULTILOGIN_DAILY_VIEW_LIMIT` | 22 | Max profile views per MLX profile per day |
| `MULTILOGIN_PROFILE_COOLDOWN_SECONDS` | 86400 | Cooldown after captcha / auth failure |
| `MULTILOGIN_RATE_LIMIT_COOLDOWN_SECONDS` | 3600 | Cooldown after rate limit (shorter) |
| `TIER1_SKIP_LOGIN_IF_SESSION_VALID` | true | Skip bot login when MLX cookies still valid |
| `TIER1_PLACEHOLDER_DENYLIST` | (empty) | Extra comma-separated placeholder URL fragments |

Failed logins refund the daily view counter so captcha/auth errors do not burn the cap.

```bash
python scripts/probe_tier1_canary.py --file docs/tier1_canary_set.json --pool-status
```

---

## CI rule

No live LinkedIn, Multilogin, or R2 in automated tests — mock only (`tests/test_*`).
