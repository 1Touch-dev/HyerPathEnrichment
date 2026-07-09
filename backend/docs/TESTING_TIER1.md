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

| Check | Needs |
|-------|--------|
| `ENABLE_TIER1` | `true` on **worker** only (API stays `false`) |
| `BROWSER_MODE` | `multilogin` in prod; `local` only for dev experiments |
| `MULTILOGIN_*` | Email, password (MD5 in code), folder id, launcher URL |
| `LINKEDIN_BOT_*` | Dummy LinkedIn account for Selenium login |
| `MULTILOGIN_SELENIUM_HOST` | `http://host.docker.internal` from Docker worker |
| `selenium` | `pip install ".[enrichers]"` or worker image with deps |
| R2 (optional) | `R2_*` creds; unset writes to `backend/.asset-cache/` |

---

## Layer 2 — Multilogin connectivity

Multilogin launcher must be running on the host (not inside Docker).

```bash
cd backend
python scripts/probe_tier1.py --connect-test
python scripts/probe_tier1.py --scrape --linkedin-url https://www.linkedin.com/in/<slug>
```

---

## Layer 3 — Docker worker (async path)

Start the stack (Tier 1 off by default):

```bash
cd backend/docker
docker compose up --build -d api worker redis postgres
```

Enable Tier 1 on the worker via env (do **not** set on `api`):

```bash
cd backend/docker
ENABLE_TIER1=true BROWSER_MODE=multilogin docker compose up -d worker
```

Worker reaches Multilogin on the host via `host.docker.internal` (`extra_hosts` in compose).

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

Poll until `status` is `completed`; expect `dossier.photo.asset_url`.

Repeat the same `linkedin_url` with query variants — second job should hit **slug cache** (no new MLX profile start in logs).

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

## Confidence scores (locked)

| Extraction | Score |
|------------|-------|
| `og:image` | 0.84 |
| DOM fallback | 0.70 |

---

## Manual canary set

Track ~20 profiles (technical / non-technical / private) in a spreadsheet:

| slug | first scrape | cache hit | notes |
|------|--------------|-----------|-------|
| | | | |

---

## CI rule

No live LinkedIn, Multilogin, or R2 in automated tests — mock only (`tests/test_*`).
