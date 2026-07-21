# Evidence: Tier 1 Multilogin live canary — Task 90

**Date (UTC):** 2026-07-17, updated 2026-07-21
**Status:** **PARTIAL — not yet PASS.** Multilogin launcher is now reachable and credentials are configured;
real bugs were found and fixed against a live run, but the full 20-profile API+worker canary has not yet
been re-verified end-to-end. See
[`../e2e-evidence/tier1-live-2026-07-21/README.md`](../e2e-evidence/tier1-live-2026-07-21/README.md) for the
full write-up (live isolation-mode PASS, the API-path bugs found/fixed, and what's still outstanding).

## 2026-07-21 update

- Multilogin X launcher reachability and credentials are **no longer the blocker** (previously they were).
- Isolation-mode scrape (Multilogin + Selenium, no API/worker) passed live, 4/4, after correcting bad
  profile slugs in the local canary set.
- The full API + RQ worker path surfaced two more real, now-fixed bugs (SQLite `database is locked` under
  concurrent writes; a stale Redis pub/sub client crashing the worker's *next* job after any job failure).
- The Multilogin daily view budget was exhausted while diagnosing/fixing the above, so the fixes have not
  yet been re-verified against a fresh full-canary run. **Task 90's live Tier 1 gate remains unsigned** until
  that re-run passes with `summary.fail == 0`.

## 2026-07-21 update, session 2 (limit raised to 40, scoped to profiles 1–10)

- `MULTILOGIN_DAILY_VIEW_LIMIT` was raised to 40 to allow a second, budget-scoped attempt against only the
  first 10 (of 20) canary profiles, with profiles 11–20 explicitly deferred to **manual verification by the
  operator** (not automated, out of scope for this branch).
- A **third real bug** was found and fixed: `Pipeline.execute_job()` set the job's `running` status on the
  ORM object without committing it, holding an uncommitted write transaction on SQLite for the entire scrape
  duration — the actual root cause behind the `"database is locked"` errors (WAL/`busy_timeout` alone didn't
  fully mask it under load). Fixed by committing the `running` transition immediately before the scrape
  starts.
- Before restarting the API+worker, a pool-status check (`probe_tier1_canary.py --pool-status`) was run to
  confirm remaining budget — but that script has **no lightweight status-only mode**: `--pool-status` only
  adds counters to the printed report; the script always runs a **full live isolation scrape of every
  profile in the input file** first. This was not caught in time, and the process was killed ~4.5 minutes in,
  by which point it had already consumed the **entire raised budget** (`views_today: 40/40` on both pool
  profiles, confirmed via a direct read-only Redis check).
- **Result: the planned 10-profile API + RQ worker re-run did not execute at all this session.** No profiles
  1–10 (or any others) were verified live through the API+worker path in session 2 — there is no PASS/FAIL
  breakdown to report. Per the task's explicit instruction, this is reported honestly rather than forced.
  **Task 90's live Tier 1 gate remains unsigned.** See
  [`../e2e-evidence/tier1-live-2026-07-21/README.md`](../e2e-evidence/tier1-live-2026-07-21/README.md) for
  full detail.
- Profiles 11–20: **pending manual verification by the operator.**

## Why originally skipped (2026-07-17, historical)

- Multilogin credentials were **not configured** on the operator host or in CI secrets for this pass.
- Tier 1 skip-live verification already passed on Windows (shape / settings path).
- Do **not** commit `backend/docs/tier1_canary_set.json` or Multilogin / LinkedIn bot secrets.

## Unblock checklist (remaining)

1. Wait for the Multilogin daily view budget to reset (Redis counters are date-keyed, reset at local
   midnight), or otherwise confirm budget is available for both pool profiles.
2. Re-run, scoped to the first 10 profiles only:
   `python backend/scripts/e2e_tier1_canary.py --file backend/docs/tier1_canary_set.json --limit 10 --json`,
   then `python backend/scripts/run_canary_score.py --tier tier1 --json`, with all three fixes from
   `fix/task90-tier1-live-canary` applied (API envelope unwrap, SQLite WAL/busy_timeout + commit-running-
   immediately, events-Redis close-per-job).
3. **Do not** use `probe_tier1_canary.py --pool-status` as a budget pre-check — it has no status-only mode
   and will run a full live scrape of every profile in `--file` before printing anything.
4. Confirm `summary.fail == 0` (or equivalent) in the resulting report(s) for profiles 1–10.
5. Save the report(s) under `backend/docs/e2e-evidence/tier1-live-<date>/` and update this file with the
   pass/fail breakdown for profiles 1–10.
6. Profiles 11–20: pending manual verification by the operator (out of scope for this branch).

## Relation to Task 90

Local/staging completion can proceed without Multilogin. **Full Task 90 / Phase 7** stays partial until this live canary passes **and** production host (86–89) is signed.
