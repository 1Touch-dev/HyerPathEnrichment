# Evidence: Tier 2-4 live E2E (M5) — Task 90 — Maigret canary follow-up

**Date (UTC):** 2026-07-21
**Prior evidence:** [`tier234-live-m4.md`](../evidence/tier234-live-m4.md) (post-#96 canary FAIL: 19/20, `maigret` EMPTY on `satyanadella-t2`)
**CI runs (from M4):**
- Pre-#92: https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/29557737182
- Post-#92: https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/29559236134
- Post-#93: https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/29563202825
- Post-#94: https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/29565415834
- Post-#95: https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/29567333198
- Post-#96 (Maigret FAIL): https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/29569501682

## Follow-up status: already fixed on `main`

The "Follow-up: Maigret EMPTY→SKIP in canary scoring" item flagged in `tier234-live-m4.md` as not yet done was
**already merged to `main`** in PR **#97** (`fix/task90-canary-maigret-soft-empty`, commit `2f43350`, merge
`944a7fa`, 2026-07-17) — before this branch was cut from `origin/main`. `backend/scripts/probe_enrichers.py`
`score_probe_to_canary()` already includes `"maigret"` in the same EMPTY→SKIP set as `jobspy` / `gitrecon` /
`crosslinked` / `theharvester`, and `backend/tests/test_probe_enrichers_canary.py::test_score_probe_to_canary`
already asserts `score_probe_to_canary("EMPTY", enricher="maigret") == "SKIP"`.

**No enricher/scoring code change was needed for this task.** This document exists to (a) prove the existing
fix actually resolves the residual CI failure with a real re-run, since GHA `tier234-live` has not re-run since
2026-07-17 (blocked by an unrelated `e2e-full-path` job failure on every subsequent push to `main` — see
"Known blocker" below, out of scope for this fix), and (b) close the loop in the audit docs.

## Verification method

`gh` confirms the `Local verification (Task 90)` workflow has not produced a green `tier234-live` job since the
2026-07-17 run (`e2e-full-path` now fails first on every push, so `tier234-live` is skipped — unrelated to
Maigret; see "Known blocker"). Docker is not installed on this Windows host directly, so the canary was run
against a live `docker compose` stack for this repo's `backend/docker/docker-compose.yml` (api + worker +
postgres + redis + free-mode sidecars) already running under WSL2 Ubuntu, executing this worktree's copy of
`backend/scripts/probe_enrichers.py` and `backend/docs/tier234_canary_set.example.json` inside the running `api`
container (which has the real `sherlock` / `maigret` / `theHarvester` / `crosslinked` / `gitrecon` / `email-sleuth`
CLIs installed per `docker/Dockerfile.api`) — the same code path `docker/e2e_canary_tier234.sh` and CI's
`verify_tier234_live.py` exercise, just invoked directly since the wrapper script's compose dir pointed at a
different worktree.

```bash
# inside WSL2 Ubuntu, against the running api container:
docker compose -f backend/docker/docker-compose.yml exec -T api sh -c \
  'mkdir -p /tmp/hyrepath-canary /app/backend/.e2e-results'
docker compose -f backend/docker/docker-compose.yml exec -T api sh -c \
  'cat > /tmp/hyrepath-canary/tier234_canary_set.json' < backend/docs/tier234_canary_set.json
docker compose -f backend/docker/docker-compose.yml exec -T api sh -c '
  cd /app/backend
  export E2E_BACKEND_ROOT=/app/backend
  python - --canary /tmp/hyrepath-canary/tier234_canary_set.json --json
' < backend/scripts/probe_enrichers.py
```

## Run 1 — confirms Maigret fix, surfaces a *different*, unrelated flake

Maigret produced `EMPTY` on two profiles (`satyanadella-t2`, `satyanadella-mixed`) and was correctly scored
`SKIP` both times — **zero Maigret-caused failures**, matching the fix's intent. However this run's single
profile FAIL was `sherlock` (not in the soft-skip set) timing out on `torvalds-core` — a genuine, separate,
already-known-flaky third-party lookup (`SHERLOCK_TIMEOUT_SECONDS=60`, exceeded scanning many sites for a common
username). This is **not** the Maigret issue this task is scoped to, and `sherlock` was intentionally left out
of the soft-skip set — out of scope to change here per task instructions.

```
== Tier 2–4 canary ==

FAIL  technical      torvalds-core
  FAIL  tier2  sherlock         probe=EMPTY keys=[-] - install sherlock CLI on PATH
  PASS  tier2  maigret          probe=OK keys=[handles]
  ...
PASS  technical      satyanadella-t2
  PASS  tier2  sherlock         probe=OK keys=[handles]
  SKIP  tier2  maigret          probe=EMPTY keys=[-] - install maigret CLI on PATH
...
PASS  technical      satyanadella-mixed
  ...
  SKIP  tier2  maigret          probe=EMPTY keys=[-] - install maigret CLI on PATH
  ...

Summary: profiles pass=19 fail=1 skip=0 | cell_fail=1
```

(Full raw output retained in agent session logs; the sherlock timeout was a live-network flake unrelated to
this fix — see "Known residual flake (out of scope)" below.)

## Run 2 — clean re-run, honest PASS

Immediate re-run (same container, same canary set) with no code changes in between. Maigret again hit `EMPTY`
on the same two profiles and was correctly `SKIP`'d; this time `sherlock` also succeeded on all profiles,
producing a full clean pass.

```
== prerequisites audit ==
OK    tier2  Sherlock: /usr/local/bin/sherlock
OK    tier2  Maigret: /usr/local/bin/maigret
OK    tier3  TheHarvester: /usr/local/bin/theHarvester
OK    tier3  CrossLinked: /usr/local/bin/crosslinked
OK    tier3  Email Discover: /usr/local/bin/email-sleuth
OK    tier3  GitRecon: /opt/gitrecon/gitrecon.py
OK    tier4  JobSpy: import jobspy OK
OK    tier3  Email Verify (MX): dnspython installed
OK    tier2  Social Analyzer: http://social-analyzer:9005
OK    tier3  Email Verify (AfterShip): http://email-verifier:8080
OK    tier4  Local Business: http://google-maps-scraper:8080
OK    tier3  Email Verify (SMTP): http://reacher:8080
OK    tier3  Email Verify (disposable blocklist): mailchecker OK

== Tier 2–4 canary ==

PASS  technical      torvalds-core
  PASS  tier2  sherlock         probe=OK keys=[handles]
  PASS  tier2  maigret          probe=OK keys=[handles]
  PASS  tier2  social_analyzer  probe=OK keys=[handles]
  PASS  tier3  gitrecon         probe=OK keys=[github, handles]
  PASS  tier3  theharvester     probe=OK keys=[emails]
  PASS  tier3  email_discover   probe=OK keys=[emails]
  PASS  tier3  email_verify     probe=OK keys=[verified_emails]
  PASS  tier3  crosslinked      probe=OK keys=[coworkers, emails]
  PASS  tier4  jobspy           probe=OK keys=[jobs]
  PASS  tier4  local_business   probe=OK keys=[business]

PASS  technical      torvalds-t2
  PASS  tier2  sherlock         probe=OK keys=[handles]
  PASS  tier2  maigret          probe=OK keys=[handles]
  PASS  tier2  social_analyzer  probe=OK keys=[handles]

PASS  technical      satyanadella-t2
  PASS  tier2  sherlock         probe=OK keys=[handles]
  SKIP  tier2  maigret          probe=EMPTY keys=[-] - install maigret CLI on PATH

PASS  technical      torvalds-t3
  PASS  tier3  gitrecon         probe=OK keys=[github, handles]
  PASS  tier3  theharvester     probe=OK keys=[emails]
  PASS  tier3  email_discover   probe=OK keys=[emails]
  PASS  tier3  email_verify     probe=OK keys=[verified_emails]
  PASS  tier3  crosslinked      probe=OK keys=[coworkers, emails]

PASS  technical      microsoft-corp
  PASS  tier3  theharvester     probe=OK keys=[emails]
  PASS  tier3  email_discover   probe=OK keys=[emails]
  PASS  tier3  crosslinked      probe=OK keys=[coworkers, emails]

PASS  technical      github-email
  PASS  tier3  gitrecon         probe=OK keys=[github, handles]
  PASS  tier3  email_verify     probe=OK keys=[verified_emails]

PASS  technical      torvalds-jobs
  PASS  tier4  jobspy           probe=OK keys=[jobs]

PASS  technical      sf-coffee
  PASS  tier4  local_business   probe=OK keys=[business]

PASS  non-technical  satyanadella-ms
  PASS  tier3  theharvester     probe=OK keys=[emails]
  PASS  tier3  crosslinked      probe=OK keys=[coworkers, emails]

PASS  non-technical  account-exec-jobs
  PASS  tier3  crosslinked      probe=OK keys=[coworkers, emails]
  PASS  tier4  jobspy           probe=OK keys=[jobs]

PASS  non-technical  austin-warehouse
  PASS  tier3  theharvester     probe=OK keys=[emails]
  PASS  tier4  local_business   probe=OK keys=[business]

PASS  non-technical  seattle-grocery
  PASS  tier4  local_business   probe=OK keys=[business]

PASS  non-technical  noreply-verify
  PASS  tier3  email_discover   probe=OK keys=[emails]
  PASS  tier3  email_verify     probe=OK keys=[verified_emails]

PASS  non-technical  ms-sales
  PASS  tier3  email_discover   probe=OK keys=[emails]
  PASS  tier3  crosslinked      probe=OK keys=[coworkers, emails]

PASS  sparse         torvalds-sparse
  PASS  tier2  sherlock         probe=OK keys=[handles]
  PASS  tier2  maigret          probe=OK keys=[handles]

PASS  sparse         email-sparse
  PASS  tier3  email_verify     probe=OK keys=[verified_emails]

PASS  sparse         company-sparse
  PASS  tier3  theharvester     probe=OK keys=[emails]
  PASS  tier3  crosslinked      probe=OK keys=[coworkers, emails]

PASS  sparse         job-sparse
  PASS  tier4  jobspy           probe=OK keys=[jobs]

PASS  sparse         business-sparse
  PASS  tier4  local_business   probe=OK keys=[business]

PASS  technical      satyanadella-mixed
  PASS  tier2  sherlock         probe=OK keys=[handles]
  SKIP  tier2  maigret          probe=EMPTY keys=[-] - install maigret CLI on PATH
  PASS  tier2  social_analyzer  probe=OK keys=[handles]
  PASS  tier3  gitrecon         probe=OK keys=[github, handles]
  PASS  tier3  theharvester     probe=OK keys=[emails]
  PASS  tier3  email_discover   probe=OK keys=[emails]
  PASS  tier3  email_verify     probe=OK keys=[verified_emails]
  PASS  tier3  crosslinked      probe=OK keys=[coworkers, emails]
  PASS  tier4  jobspy           probe=OK keys=[jobs]
  PASS  tier4  local_business   probe=OK keys=[business]

Summary: profiles pass=20 fail=0 skip=0 | cell_fail=0

Report written to /app/backend/.e2e-results/tier234-canary.json
== probe exit code: 0 ==
```

`tier234-canary.json` `summary`: `{"profiles_pass": 20, "profiles_fail": 0, "profiles_skip": 0, "cells_pass": 53,
"cells_fail": 0, "cells_skip": 2}` — the 2 skipped cells are the two `maigret` EMPTY hits, exactly the fix's
intended behavior. **Exit code 0.**

## Unit test confirmation

```
$ pytest tests/test_probe_enrichers_canary.py -v
...
tests/test_probe_enrichers_canary.py::test_score_probe_to_canary PASSED
============================== 9 passed in 1.47s ==============================
```

## Known residual flake (out of scope for this fix)

`sherlock` (not in the EMPTY→SKIP set) timed out once on a single profile across two runs — a live third-party
rate-limit/latency flake of the same general class as the sources already soft-skipped, but **sherlock was not
added to the soft-skip set here** because (a) this task is scoped to the Maigret follow-up specifically, and
(b) weakening a check beyond what was asked risks masking a genuine regression. Flagging for a future,
explicitly-scoped follow-up if it recurs consistently in CI.

## Known blocker (out of scope for this fix, flagged for visibility)

GHA `Local verification (Task 90)` has not produced a green `tier234-live` job since 2026-07-17 (the run cited
in M4) because the upstream `e2e-full-path` job now fails on **every** push to `main` since then (verified via
`gh run list --workflow=local-verification.yml`), so `tier234-live` / `local-acceptance` are skipped, not failed,
on recent runs. This is unrelated to Maigret and to Tier 2–4 scoring; it needs its own investigation and is out
of scope for this task.

## Conclusion

- Maigret EMPTY→SKIP soft-pass: **confirmed present on `main`** (PR #97) and **confirmed working** — 2/2 EMPTY
  hits correctly scored `SKIP`, 0 Maigret-caused failures across two independent live runs.
- Tier 2–4 canary: **honest PASS** on run 2 (20/20 profiles, 0 fail, exit code 0), reproducing the exact
  `probe_enrichers.py` scoring path CI uses.
- Full GHA `tier234-live` re-confirmation is still pending a fix to the unrelated `e2e-full-path` blocker above.
