# Evidence: Document job status fix — real e2e proof (success / in-task failure / worker-crash paths)

**Date (UTC):** 2026-08-14
**Scope:** Real, non-mocked end-to-end proof of the document-processing job-status fix (`backend/app/workers/tasks/document.py`, `backend/app/modules/documents/service.py`) against a real Postgres + Redis + uvicorn + RQ-worker stack — not unit/integration tests with mocked Redis/DB.

## Setup: real stack under WSL2

Ran locally under WSL2 Ubuntu + Docker Engine (see [`setup_stack.sh`](setup_stack.sh)):

1. `docker compose -f backend/docker/docker-compose.yml up -d postgres redis` — real Postgres 16 + Redis 7 containers (`docker-postgres-1` / `docker-redis-1`, ports 5433/6379 on localhost), waited for Docker healthchecks.
2. Python venv at `~/hyre-e2e-venv` (native ext4, not the `/mnt/g` NTFS-via-9p mount, for speed) with `pip install -e backend`.
3. `alembic upgrade head` against the real Postgres — reached `025_merge_job_match_heads (head)`.
4. Real `uvicorn app.main:app` (background, `/health` → 200) and a real `rq worker document_processing` process (background) — no `LocalStack`/`fakeredis`/mocked queue.

**Fix needed:** `backend/.env.production` is CRLF (Windows-authored). Bash chokes on trailing `\r` in sourced values, which made Pydantic reject settings like `ENABLE_TIER1='false\r'`. Fixed by piping the file through `tr -d '\r'` into a temp file before `source`-ing it (see `setup_stack.sh` step 4/7).

## Test flow (all 3 proofs use the real HTTP API, not direct DB/queue manipulation)

For each proof point: register a fresh user → fetch the real verification token from Postgres (`email_verification_tokens` table, since `EMAIL_TEST_MODE=true` skips actually sending mail) → verify → login (real JWT cookie) → `POST /api/documents/upload` → poll `GET /api/documents/jobs/{job_id}`.

## Result: PROOF 1 — success path — PASS

Script: [`run_e2e_tests.sh`](run_e2e_tests.sh) (registration through Proof 1/2). Full output: [`terminal-output.txt`](terminal-output.txt), Part 2/3.

- Uploaded `backend/tests/fixtures/sample_cv.pdf` (real, valid PDF) via `POST /api/documents/upload?document_type=cv`.
- `job_id=c0aa8faf-70a4-4d4d-91f9-4969ed620e17`
- The worker extracted text via PyMuPDF and completed the job live during this run, but that specific worker-log line is **not** preserved in the captured `terminal-output.txt` transcript — the claim below (the poll result) is what's actually backed by the transcript.
- Polled `GET /api/documents/jobs/{job_id}` → **`status` transitioned `pending` → `completed`** with `progress=1.0`. This is the exact behavior the fix targets: the `DocumentJob` row (not just `CandidateDocument.processing_status`) is updated on success, and this transition **is** present in `terminal-output.txt`, Part 2/3.

## Result: PROOF 2 — in-task failure path — PASS

Same script/run. Full output: [`terminal-output.txt`](terminal-output.txt), Part 2/3.

- Uploaded `backend/tests/fixtures/malformed.pdf` — a file with a valid `application/pdf` MIME type (passes `DocumentService.upload_document`'s `ALLOWED_MIME_TYPES` check) but invalid/garbage PDF bytes internally, so it fails during real PyMuPDF extraction, not at the API boundary.
- `job_id=8e435de3-28d4-4acc-bd3c-63074829aa9b`
- The worker hit a genuine PyMuPDF parsing failure, surfaced as `app.services.document_processor.DocumentProcessingError` and caught by `_process_document_job`'s in-task `except Exception` handler — observed live during this run, but the specific exception-chain log text is **not** preserved in the captured `terminal-output.txt` transcript. The claim below (the poll result) is what's actually backed by the transcript.
- Polled `GET /api/documents/jobs/{job_id}` → **`status` transitioned `pending` → `failed`**, with `error` populated (`"Failed to process PDF: Failed to open stream"` chain). Confirms the in-task exception handler (not just the RQ-level `on_failure` safety net) correctly marks the job failed with a real error message, and this transition **is** present in `terminal-output.txt`, Part 2/3.

## Result: PROOF 3 — worker crash / abandoned-job path — PASS (after 2 failed attempts; root causes documented below)

Final script/run: [`run_proof3.sh`](run_proof3.sh). Full output: [`terminal-output.txt`](terminal-output.txt), Part 3/3.

**Method:** started a real `rq worker` process, `SIGSTOP`'d it (froze it, cannot dequeue), uploaded a real valid PDF (`test_cv_v2.pdf`) while frozen, confirmed the job was still `pending` (proves it had not been picked up), then `SIGCONT`'d the worker, waited **4 seconds** (long enough for the worker to dequeue and genuinely begin executing — confirmed via the worker's own dequeue log line, `document_processing: app.workers.tasks.document.process_document_job(...)`, with no completion line before the kill), then `SIGKILL`'d the worker process (simulating a hard crash mid-job, not a timeout).

- `job_id=97c25060-3c7d-4d85-adbb-d2bde3ff1250`
- Immediately after the kill: `GET /api/documents/jobs/{job_id}` still showed `status=pending` (correctly not yet resolved — no zombie worker is left to "notice" its own death).
- Waited ~110s for RQ's `StartedJobRegistry` heartbeat-TTL to expire. For `rq==2.10.0`, the registry TTL a job is given is `min(job.timeout, job_monitoring_interval) + 60` = `min(300, 30) + 60` = **90s** from job start (confirmed by reading the installed `rq` source directly — `Worker.get_heartbeat_ttl` in `rq/worker/base.py`), independent of the app's 300s `job_timeout`. No code change or env var override was needed to get a fast, real trigger.
- Started a **new** `rq worker` process (new PID, no state carried over from the killed one). Its very first `should_run_maintenance_tasks` pass (runs on worker startup) called `clean_registries` → `StartedJobRegistry.cleanup()`, which found the job's heartbeat expired, raised `AbandonedJobError`, and called `job.execute_failure_callback(...)` — i.e. our app's real `on_document_job_failure` RQ callback, registered via `Callback("app.workers.tasks.document.on_document_job_failure", timeout=30)` in `DocumentService.upload_document`.
- Fresh worker's log: `Document job failed at the RQ worker level (timeout or crashed/abandoned worker)` / `StartedJobRegistry cleanup: ... Moved to FailedJobRegistry, due to AbandonedJobError`.
- Polled `GET /api/documents/jobs/{job_id}` → **`status` transitioned `pending` → `failed`**, `error="Worker-level failure: AbandonedJobError: "`. This is the exact safety-net path the fix's `on_document_job_failure` callback exists for: a worker that dies without ever running the in-task `except` block still leaves the client-visible `DocumentJob.status` correctly resolved to `failed`, not stuck at `pending` forever.

### Two earlier failed attempts at Proof 3 (kept in the log for honesty; root causes below — not implementation bugs)

`terminal-output.txt` only contains the final, successful Proof 3 run. Two earlier attempts were made in this session and discarded once root-caused; they are **not** included in the assembled terminal-output.txt (which would have been misleading), but are reported here for completeness:

1. **First attempt** (part of the original `run_e2e_tests.sh`, before it was trimmed down to Proofs 1+2 for the final transcript): killed the worker with `pkill -9` immediately after `SIGCONT`, with zero delay. The job was still sitting in RQ's *intermediate queue* (enqueued, not yet dequeued) at the moment of the kill, not in `StartedJobRegistry`. RQ's `IntermediateQueue.cleanup()` (a different code path from `StartedJobRegistry.cleanup()`) does mark such jobs `failed` at the RQ level, but — confirmed by reading `rq/intermediate_queue.py` — it does **not** call `job.execute_failure_callback(...)`, so our `on_document_job_failure` never ran and the `DocumentJob` row stayed `pending`. This is a real RQ behavior difference between "job crashed while queued-but-not-started" vs "job crashed while started" — not a bug in the fix under test.
2. **Second attempt**: fixed the timing (using a Redis-status tight-poll to wait for `status=started` before killing), but the polling loop itself (spawning a fresh `docker exec redis-cli KEYS` scan per shell iteration) was too slow to reliably catch the job in time, and was abandoned in favor of the deterministic fixed-delay approach that succeeded (documented above). No implementation issue found.
3. **Unrelated tooling bug found and fixed along the way**: the second attempt's fresh worker process was started without exporting `DATABASE_URL`/`REDIS_URL`/etc, so `SyncSessionLocal` (used by `on_document_job_failure`) fell back to the app's default SQLite settings instead of the real Postgres the rest of the stack used, causing `sqlite3.OperationalError: no such table: document_jobs` inside the callback. This was a test-harness configuration bug (missing env export in my own script), not an application bug — fixed by exporting the same `DATABASE_URL`/`REDIS_URL`/etc before starting any worker process, consistently with `setup_stack.sh`.

## Cleanup state

At the end of this run, the following were stopped:

- All `rq worker document_processing` processes (`pkill -9 -f "rq worker document_processing"`).
- The uvicorn process (PID recorded in `~/hyre-e2e-uvicorn.pid` on the WSL side) — stopped via `kill`.
- `docker compose -f backend/docker/docker-compose.yml down` for the `postgres`/`redis` containers (`docker-postgres-1`, `docker-redis-1`), including their volumes.

No stack was left running after this task. If anything is still up when you read this, it means teardown ran after this document was written — check `docker ps` and `ps aux | grep -E 'uvicorn|rq worker'` under `wsl -d Ubuntu` to confirm current state.

## Reproduce

```bash
# WSL2 Ubuntu, Docker Engine
wsl -d Ubuntu bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docs/e2e-evidence/2026-08-14-document-job-status-fix/setup_stack.sh
wsl -d Ubuntu bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docs/e2e-evidence/2026-08-14-document-job-status-fix/run_e2e_tests.sh   # Proofs 1 + 2
wsl -d Ubuntu bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docs/e2e-evidence/2026-08-14-document-job-status-fix/run_proof3.sh      # Proof 3
```
