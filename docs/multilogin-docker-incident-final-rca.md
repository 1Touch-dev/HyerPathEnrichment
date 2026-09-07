# Multilogin Docker Incident - Final RCA

## 1. Executive Summary

**Verdict:** `FIXED - PARTIAL RUNTIME VERIFICATION`

Multilogin was failing because the repo allowed multiple conflicting Tier 1 startup topologies, and the broken family could still look superficially valid. The main failure mode was starting Tier 1 with a worker/runtime shape that did not match the shipped `WORKER_QUEUE_MODE=per_tier` contract or the Linux MLX host-network contract.

It appeared intermittent because operators could switch between startup families, leave previously healthy containers running, or validate only a partial stack, which masked the broken topology.

Previous restarts sometimes helped because they changed which worker family was active, cleaned up stale containers, or temporarily restored a compatible queue-consumer/runtime combination without fixing the underlying contract drift.

The permanent remediation in this branch is to:

- enforce one supported Linux MLX production family
- fence the deprecated `docker-compose.tier1.yml` path as diagnostic-only
- align queue ownership, env templates, startup validation, docs, and proof harnesses
- add focused regression tests for startup selection, env validation, queue ordering, scheduler/consumer ownership, and proof-harness activation

This branch **does not** claim a fresh real Linux-host `worker-tier1 -> multilogin -> LinkedIn` end-to-end proof from this Windows/WSL environment. That remains an external operational validation step.

## 2. Supported Runtime Architecture

```text
Docker host (native Linux target for full MLX proof)
|
|- api                         bridge network
|- redis                       bridge network
|- postgres                    bridge network, host-published 127.0.0.1:5433
|- social-analyzer             bridge network
|- google-maps-scraper         bridge network
|- email-verifier              bridge network
|- worker                      bridge network, auxiliary queues + enrichment
|- worker-email                bridge network, email queue
|- worker-cleanup              bridge network, orphan-job maintenance
|- worker-job-matching         bridge network, job_matching queue + scheduler seeding
|- worker-tier234             bridge network, tier234 queue
|- worker-tier1               host network, tier1 queue
`- multilogin                 host network, launcher + profile ports
```

Supported Linux MLX family:

```text
docker-compose.yml
+ docker-compose.prod.yml
+ docker-compose.foundation.yml
+ docker-compose.tier-workers.yml
+ docker-compose.multilogin.yml
```

Primary contract points:

- `worker-tier1` is the **only** host-network Tier 1 worker
- `multilogin` is the host-network Multilogin container
- `worker` owns auxiliary queues, including `audio_cleanup`
- `worker-job-matching` owns the `job_matching` queue and scheduler seeding
- real Linux Tier 1 now fails closed unless `--with-linux-mlx` or `ENABLE_LINUX_MLX=true` selects the supported family

## 3. Exact Root Cause

Multilogin failed because the project allowed unsupported Tier 1 startup combinations that mixed:

- the legacy `docker-compose.tier1.yml` diagnostic path
- the Linux MLX host-network path
- the shipped `WORKER_QUEUE_MODE=per_tier` contract

without enforcing one coherent worker/queue/runtime topology.

It appeared intermittent because different startup commands, leftover containers, and partial validations could temporarily leave a working consumer or compatible topology in place even when the chosen startup family was wrong.

Restarting or recreating containers sometimes helped because it changed which queue consumers were present and which compose family was effectively active, but it did not eliminate the configuration drift that allowed the broken family in the first place.

The permanent fix is to make the supported Linux MLX topology explicit and enforce it across:

- `start_production.sh`
- `validate_env.sh`
- env templates
- queue ownership
- compose overlays
- docs and operator examples
- proof-harness wiring

## 4. Minimal Reproduction

Smallest convincing reproduction of the contract failure class:

1. Use a production-shaped env with `WORKER_QUEUE_MODE=per_tier`
2. Start a non-supported Tier 1 family, or present base/manual startup as if it were a valid async worker shape
3. Observe queue consumers or Tier 1 runtime assumptions no longer match the selected compose family

Representative broken patterns that this branch now fences off:

- Linux Tier 1 without `--with-linux-mlx`
- legacy `docker-compose.tier1.yml` used as if it were a supported production path
- worker/queue startup that implies a generic `worker` can safely run under `per_tier` without the proper family around it

## 5. Working vs Broken

| Component | Broken State | Fixed State |
| --- | --- | --- |
| Tier 1 startup family | Multiple contradictory families treated as valid | Supported family explicitly `prod + foundation + tier-workers + multilogin` |
| Tier 1 runtime selection | Linux Tier 1 could start without Linux MLX | Real Linux Tier 1 fails closed unless Linux MLX is enabled |
| Queue consumers | `job_matching`, `audio_cleanup`, and auxiliary ownership drifted across docs/code | Queue ownership and worker roles are explicit and tested |
| Worker topology docs | Base/manual examples implied unsupported async worker shapes | Base/manual examples labeled partial/diagnostic; supported production path points to tier-worker family |
| Proof harness | Real-infra scripts used stale container assumptions and weak selector wiring | Harness uses compose service targeting and explicit `PYTEST_USE_REAL_INFRA` contract |

## 6. Root Causes

### ROOT-ML-001

**Severity:** P1
**Classification:** ROOT CAUSE

Unsupported Tier 1 startup families were allowed to coexist with the shipped `per_tier` worker contract, so operators could launch a topology that looked plausible but did not match queue ownership or Linux MLX requirements.

**Evidence**

- startup-script and env-validation regressions added in this branch
- compose-family selection/dry-run checks
- queue-order and worker-contract tests
- reviewer findings across startup, docs, and proof harnesses

**Why intermittent**

Different startup commands and leftover containers could leave a seemingly healthy subset of consumers or services active, masking the broken family.

**Fix**

- fail closed on real Linux Tier 1 without Linux MLX
- route supported production to `foundation + tier-workers + multilogin`
- align docs and templates with that contract

## 7. Contributing Causes

### CONTRIB-ML-001

**Classification:** CONFIG DRIFT
**Severity:** P2

Env templates, compose overlays, startup validation, and operator docs drifted apart over time.

### CONTRIB-ML-002

**Classification:** DOCUMENTATION DRIFT
**Severity:** P2

Several docs and scripts continued to teach the deprecated `docker-compose.tier1.yml` family after the Linux MLX topology became the supported target.

### CONTRIB-ML-003

**Classification:** OBSERVABILITY GAP
**Severity:** P2

The proof harnesses and startup checks were not trustworthy enough to prove the intended contract and initially created false confidence.

## 8. Connectivity / Validation Matrix

| Check | Status | Notes |
| --- | --- | --- |
| Supported Linux MLX dry-run family resolves | PASS | Verified in WSL against the supported compose family |
| Supported Linux MLX compose config merges | PASS | Verified with example envs |
| Startup/env contract regressions | PASS | Script and validator regressions added and passing |
| LinkedIn send/sourcing regressions | PASS | Focused backend suites green |
| Job-matching regressions | PASS | API and scheduler/queue ownership covered |
| Audio-cleanup regressions | PASS | Auxiliary queue ownership covered |
| Proof-harness selector/collection path | PASS | Real-infra path now collects with explicit plugin/env contract |
| Real Linux-host MLX end-to-end scrape | BLOCKED | Not executed from this Windows/WSL environment |

## 9. Failure Masking

During investigation, we confirmed the codebase had places where infrastructure errors could degrade into softer outcomes. That was a meaningful incident-risk observation, but the final branch work concentrated on the proven startup/runtime contract drift that repeatedly allowed the wrong Tier 1 topology to be treated as acceptable.

Failure masking should still be treated as a residual diagnostic risk area, but it was **not** the primary proven root cause for this incident.

## 10. Changes Applied

The branch changes cover six main areas:

1. **Startup contract enforcement**
   - `backend/scripts/start_production.sh`
   - `backend/scripts/validate_env.sh`

2. **Compose/runtime alignment**
   - `backend/docker/docker-compose*.yml`
   - `backend/docker/Dockerfile.multilogin`
   - `backend/docker/entrypoint-worker.sh`

3. **Worker / queue ownership**
   - `backend/app/workers/queue.py`
   - `backend/app/workers/rq_worker.py`
   - `backend/app/workers/rq_worker_job_matching.py`
   - `backend/app/modules/job_matching/service.py`

4. **Proof harness repair**
   - `backend/docker/run_real_infrastructure_tests.sh`
   - `backend/docker/run_real_infrastructure_tests.ps1`
   - `backend/tests/conftest.py`
   - `backend/tests/conftest_real_infrastructure.py`
   - `backend/tests/test_foundation_week1_integration.py`
   - `backend/tests/test_real_infrastructure_harness.py`

5. **Regression coverage**
   - `backend/tests/test_start_production_script.py`
   - `backend/tests/test_validate_env_script.py`
   - `backend/tests/test_queue_routing.py`

6. **Documentation / operator cleanup**
   - deployment, networking, testing, architecture, rebuild, and runbook docs touched to remove or fence deprecated paths

## 11. Tests

Representative focused validations that passed during this branch:

- `backend/tests/test_start_production_script.py`
- `backend/tests/test_validate_env_script.py`
- `backend/tests/test_queue_routing.py`
- `backend/tests/test_job_matching_api.py`
- `backend/tests/test_phase2_rate_limits.py`
- `backend/tests/test_linkedin_send.py`
- `backend/tests/test_linkedin_sourcing.py`
- `backend/tests/test_audio_cleanup.py`
- `backend/tests/test_real_infrastructure_harness.py`

Real-infra selector proof:

- `tests/test_foundation_week1_integration.py` collects under explicit `PYTEST_USE_REAL_INFRA=true` and `-p tests.conftest_real_infrastructure`

## 12. Validation Result

**Current branch status:** code/test/contract remediation complete, with external operational proof still pending.

This means the correct final classification for this repo-side work is:

`FIXED - PARTIAL RUNTIME VERIFICATION`

not

`FIXED AND VERIFIED`

because the branch does not include a fresh native Linux-host `worker-tier1 -> multilogin -> LinkedIn` end-to-end proof run.

## 13. Remaining Risks

### Fixed

- deprecated Tier 1 startup family taught as supported production path
- split/ambiguous queue ownership for auxiliary, `job_matching`, and `audio_cleanup`
- weak or misleading proof-harness activation
- env-template / validation drift for Linux MLX startup

### Blocked / External

- fresh real Linux-host Tier 1 end-to-end proof using the supported Linux MLX family

### Room For Improvement

- existing pytest-asyncio and Python 3.13 deprecation warnings
- residual diagnostic risk from some historical failure-masking paths outside the primary root cause

## 14. Final Statement

Multilogin was failing because the codebase and operator docs allowed unsupported Tier 1 startup families to coexist with the shipped `per_tier` worker contract and Linux MLX requirements.

It appeared intermittent because different startup commands, partial validations, and leftover containers could temporarily leave a working subset of consumers or services in place.

Restarting/recreating services helped only by changing the active topology, not by fixing the underlying contract drift.

This branch fixes that contract drift across startup scripts, env validation, compose overlays, worker ownership, proof harnesses, and operator docs.

What remains is the final external validation step on a real Linux host to prove the supported Linux MLX topology end-to-end with a live `worker-tier1 -> multilogin -> LinkedIn` run.
