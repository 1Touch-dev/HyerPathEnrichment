# Tier 1 Multilogin live canary — 2026-07-21

**Status: PARTIAL — real bugs found & fixed, isolation-level scrape verified live, full API+worker canary NOT yet re-verified (daily Multilogin view budget exhausted).**

This is **not** a claim of a full Task 90 live-canary PASS. It documents a genuine live run against the real
Multilogin X launcher + LinkedIn, the real bugs that run uncovered, the fixes applied, and exactly what is
still outstanding before the 20-profile end-to-end canary can be signed off.

## Environment

- Windows host, Multilogin X desktop launcher running and reachable at `https://127.0.0.1:45001` (confirmed
  via `curl.exe -sk https://127.0.0.1:45001/api/v2/` → HTTP 404, expected).
- `backend/.env` populated with real `MULTILOGIN_*` / `LINKEDIN_BOT_*` credentials (never printed/committed).
- `ENABLE_TIER1=true`, `BROWSER_MODE=multilogin`, `MULTILOGIN_SELENIUM_HOST=http://127.0.0.1`.
- API (`uvicorn`) and RQ worker run natively on the host (not Docker), per `backend/docs/TESTING_TIER1.md`.
- `backend/docs/tier1_canary_set.json`: 20 real public LinkedIn profile URLs (gitignored, not committed).

## What passed live

### 1. Prerequisites + connectivity (Layer 1)

```
python scripts/probe_tier1.py --prereqs        # PASS — all required env vars present
curl.exe -sk https://127.0.0.1:45001/api/v2/   # HTTP 404 (launcher reachable)
python scripts/probe_tier1.py --connect-test   # PASS — sign-in, profile acquire/start,
                                                #        Selenium connect, LinkedIn feed loaded, stop
```

### 2. Single-profile live scrape (Layer 2)

```
python scripts/probe_tier1.py --scrape --linkedin-url https://www.linkedin.com/in/<public-profile>
```
Returned real photo bytes, content type, and a non-zero confidence score — the Multilogin + Selenium +
photo-extraction pipeline works end-to-end for a single profile.

### 3. Isolation-mode canary retry — 4/4 PASS

After discovering (see "Bugs found and fixed" below) that 4 of the 20 canary profiles had incorrect
LinkedIn slugs, the corrected 4 profiles were re-run in isolation mode (direct `LinkedInBrowserClient`
scrape, no API/worker in the loop):

```
python scripts/probe_tier1_canary.py --file docs/tier1_retry_set.json --pool-status --json
```

Result: **`isolation-retry-4profiles-PASS.json`** — `summary.fail == 0`, all 4 corrected profiles
(`williamhgates`, `owinfrey`, `garyvaynerchuk`, `ariannahuffington`) returned real photo bytes via
`dom_fallback` extraction with `confidence=0.7`.

## What did NOT pass yet — full API + worker canary

Running the same 4 profiles through the full HTTP API → RQ worker → pipeline path
(`scripts/e2e_tier1_canary.py --file docs/tier1_canary_set.json --json`) surfaced **two additional, real
bugs** in the API/worker path itself (both fixed — see below), captured in
**`api-canary-prefix-FAIL.json`** (`summary.fail == 4`, generated before the fixes below were applied):

- 2 jobs failed outright with `sqlite3.OperationalError: database is locked` while writing to `photo_cache`
  (API and worker both hitting the same SQLite file concurrently).
- 2 jobs completed with no error but the persisted dossier had no photo (`asset_url` missing) — a
  downstream symptom of the same worker process being left in a bad state after an unhandled
  `RuntimeError: Event loop is closed` from a stale Redis pub/sub client on the *next* job.

Both root causes were fixed in this branch (SQLite WAL/`busy_timeout` + closing the dedicated events-Redis
client per job — see "Bugs found and fixed"). However, by the time these fixes landed, the Multilogin daily
view budget (`MULTILOGIN_DAILY_VIEW_LIMIT=22` per profile, 2 profiles in the pool) was **fully exhausted**
from the isolation-mode debugging + this failed API run — both profiles show `views_today: 22, daily_limit:
22, eligible: false` as of the end of this session. Per the task's explicit instruction, rate-limit
protections were **not** disabled to force a run through.

**Net result: the SQLite-lock and event-loop bugs that caused every API-path job to fail have real fixes on
this branch, but those fixes have not yet been re-verified against a fresh live run** (the isolation-mode
scrape — which doesn't touch the API/worker/DB path at all — did pass 4/4 after the slug fixes, proving the
Multilogin/Selenium layer itself is healthy).

## Bugs found and fixed (this branch)

1. **`e2e_tier1_canary.py` didn't unwrap the API's `{success, data}` response envelope**
   (`EnvelopeAPIRoute`), so every health/sync-guard/enqueue/poll check silently read from the wrong shape.
   Fixed with an `unwrap_envelope()` helper applied at all four call sites.
2. **4 of 20 canary profiles had wrong LinkedIn slugs** (guessed rather than verified), e.g. `billgates` →
   correct is `williamhgates`; `oprahwinfrey` → `owinfrey`; `garyvee` → `garyvaynerchuk`; `ariannahuff` →
   `ariannahuffington`. These loaded real 404/authwall pages, not the intended profiles. Corrected in the
   local (gitignored) `tier1_canary_set.json`.
3. **`probe_tier1_canary.py`'s `CanaryRow` had no `expect_photo` field**, so profiles that legitimately
   should not surface a photo (`category="private"`) were scored as failures. Added `expect_photo` and
   scoring against the row's expectation rather than raw scrape success.
4. **`scrape_on_driver` misclassified slow-rendering 404/authwall/captcha pages as `NO_IMAGE`.** The SPA can
   still be rendering when the page state is first checked right after `driver.get()`; if the profile-photo
   DOM wait then times out, the page had often *since* settled into a real 404/authwall. Now re-checks page
   state after the timeout so these are classified correctly (`NOT_FOUND`/`AUTH_REQUIRED`) instead of a
   misleading `NO_IMAGE`.
5. **SQLite `"database is locked"` under concurrent API + worker writes.** SQLite's default rollback-journal
   mode takes an exclusive lock on writes; the worker's `photo_cache` insert collided with concurrent API
   reads. Fixed by enabling WAL journal mode + a 30s `busy_timeout` for SQLite connections in
   `app/database/session.py`.
6. **RQ worker crashed on the job *after* the one that failed** with `RuntimeError: Event loop is closed`.
   `app/workers/tasks/enrichment.py` closed the shared Redis client per job but not the dedicated
   `job_events` pub/sub client, leaving a stale client bound to a dead event loop that broke the next job's
   `publish_job_status` call. Fixed by calling `close_events_redis()` in the same `finally` block.
7. **Multilogin daily views were burned even when `start_profile` failed before any LinkedIn page was
   actually viewed** (e.g. a profile stuck "active" from a previous crashed session). `ProfilePool.acquire()`
   charges a view up front; added `refund_view()` calls in `LinkedInBrowserClient._scrape_with_profile`'s
   `MultiloginError`/`Exception` handlers so a failed launch doesn't cost a real view.

## Session 2 (same day, 2026-07-21): pipeline deadlock fix + accidental budget exhaustion

`MULTILOGIN_DAILY_VIEW_LIMIT` was raised from 22 to 40 to allow a second attempt, scoped to only the first
10 canary profiles (operator would manually verify profiles 11–20). Before re-running, a **third real bug**
was diagnosed and fixed:

### Bug found and fixed: pipeline-level SQLite write-lock held for the entire scrape

`Pipeline.execute_job()` (`app/enrichers/pipeline.py`) set `job.status = JobStatus.running.value` on the
in-memory ORM object but never committed it — SQLAlchemy's autoflush opened an uncommitted write transaction
on that session that stayed open for the **entire** browser scrape (30–90s per profile). The LinkedIn-photo
enricher's `PhotoCache` uses a *separate* `SessionLocal()` and tried to write to `photo_cache` mid-scrape,
colliding with the pipeline's long-held, uncommitted lock — this was the real mechanism behind the
`"database is locked"` errors from session 1, and WAL/`busy_timeout` alone couldn't fully mask it under load.
**Fix:** commit the `running` status transition immediately via `self.jobs.mark_status(job, JobStatus.running)`
before starting the scrape, so the pipeline's session holds no open write transaction while the enricher runs.
This fix is on this branch but **has not yet been re-verified against a live API+worker run** (see below).

### Operator error: `--pool-status` does not skip the canary run, and it burned the entire raised budget

Before restarting the API+worker, the plan was to first check remaining view budget with:

```
python scripts/probe_tier1_canary.py --file docs/tier1_canary_set.json --pool-status --json
```

This was a mistake: `--pool-status` only controls whether pool counters are *printed alongside* the report —
the script unconditionally runs `run_canary()` first, which does a **live isolation-mode scrape of every
profile in the file** (all 20, not 10). Because `probe_tier1_canary.py` buffers all output until the loop
finishes, no progress was visible in the terminal. By the time this was recognized (~4.5 minutes in) and the
process was force-killed, the entire newly-raised budget was already gone:

```json
[
  {"profile_id": "<redacted-mlx-profile-uuid-1>", "views_today": 40, "daily_limit": 40, "in_cooldown": false, "eligible": false},
  {"profile_id": "<redacted-mlx-profile-uuid-2>", "views_today": 40, "daily_limit": 40, "in_cooldown": false, "eligible": false}
]
```

(Confirmed via a direct, read-only `ProfilePool().pool_status()` call against Redis — no new scrape was run
to check this.) Both profiles show `eligible: false`, `in_cooldown: false` — this is normal daily exhaustion,
not a lockout; the Redis counters are keyed by date and will reset automatically at local midnight.

**Consequence: the planned 10-profile API + RQ worker re-run never executed.** No job was enqueued through
the API for this session, so there is **no PASS/FAIL breakdown to report for profiles 1–10** from this
attempt — the isolation-mode script that accidentally ran instead was killed mid-loop before it printed or
persisted any per-profile results, so there is no reliable partial-completion count either. Per the task's
explicit instruction, this is reported honestly rather than forced or faked: **no new live-verification
evidence was produced in session 2**, only the pipeline deadlock fix (code-only, unverified live) and this
budget-exhaustion record.

## Outstanding work (not done in this session)

- Re-run `python scripts/e2e_tier1_canary.py --file docs/tier1_canary_set.json --limit 10 --json` and
  `python scripts/run_canary_score.py --tier tier1 --json` against the **first 10 profiles** once the daily
  Multilogin view budget resets, to confirm `summary.fail == 0` end-to-end through the real API + worker path
  with all three fixes in this branch applied (envelope unwrap, SQLite WAL/busy_timeout +
  commit-running-immediately, events-Redis close-per-job).
- **Do not** run `probe_tier1_canary.py` again without first trimming the input file to the intended profile
  count — it has no `--limit` flag and always scrapes every row in `--file`.
- Profiles 11–20 remain **pending manual verification by the operator** — not automated, out of scope for
  this branch.
- Until the 10-profile API+worker re-run happens and passes, Task 90's live Tier 1 gate should remain **not
  signed off** — see the updated `backend/docs/evidence/tier1-multilogin-canary-skip.md`.

## Files in this folder

- `isolation-retry-4profiles-PASS.json` — real live PASS, isolation mode, 4 corrected profiles (session 1).
- `api-canary-prefix-FAIL.json` — real live run that surfaced the SQLite-lock / event-loop bugs (session 1,
  pre-fix).
- No credentials, tokens, or `.env` values appear in any file in this folder (profile IDs are Multilogin
  profile UUIDs, not secrets).
