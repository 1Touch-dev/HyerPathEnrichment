# Development plan

Phased, actionable checklist for Hyrepath Enrichment. Derived from [`backend/docs/ARCHITECTURE.md`](../backend/docs/ARCHITECTURE.md) and remaining Developer Guide gaps. This is a **delivery tracker**, not an architecture dump — verify behavior in `backend/app/` and the Implementation status table before coding.

**How to use:** Check boxes when the acceptance criteria are met in `main`. Do not mark a phase done while dependent guide gaps below are still open.

**Primary references**

| Doc | Role |
|-----|------|
| [`backend/docs/ARCHITECTURE.md`](../backend/docs/ARCHITECTURE.md) | Agent quick reference, implementation status, request flow |
| [`backend/docs/LEGAL.md`](../backend/docs/LEGAL.md) | Compliance posture, opt-out/DSAR, product boundaries |
| [`backend/scripts/smoke_test.py`](../backend/scripts/smoke_test.py) | Operator smoke entrypoint (expand beyond `/health` — guide gap 77) |
| Root `Makefile` *(planned)* | Guide gaps 1 + 79 — `setup` / `up` / `down` / `test` / `smoke` / `migrate` |
| [`RULE.md`](../RULE.md) | Reuse, no redundancy, safety before any code change |
| [`GRILLME.md`](../GRILLME.md) | Challenge-mode readiness before launch milestones |

---

## Phase 0 — Foundations (largely done)

Scaffold that later phases assume. Confirm against Implementation status before reopening.

- [x] FastAPI + Bearer auth for enrichment routes
- [x] Redis + RQ async queue (`POST /enrich` → worker; `/enrich/sync` inline)
- [x] Pipeline orchestrator with tier dispatch, merge, partial failure
- [x] Provider layer (`app/providers/`) with free→paid mode flags
- [x] Postgres in Docker (Alembic + JSONB); SQLite local default
- [x] Opt-out / DSAR public with IP rate limits; enrichment still Bearer-protected — see [`LEGAL.md`](../backend/docs/LEGAL.md)
- [x] Audit logs + purge-on-opt-out / DSAR deletion
- [x] Shape / fake-sidecar / compose E2E harnesses (`tests/`, `e2e_*.sh`)

**Exit:** New work starts from a green local or compose stack, not from re-scaffolding auth/queue/DB.

---

## Phase 1 — Developer experience (guide 1, 79, 77, 82, 84)

Make “clone → run → verify” one path. **These items are open until merged and verified on `main`.**

- [ ] **Makefile (gaps 1 + 79)** — Root `Makefile` with at least: `setup`, `up`, `down`, `test`, `smoke`, `migrate`, `help`. README Getting started should point at `make …`, not only raw compose/uvicorn.
- [ ] **Smoke beyond health (gap 77)** — Expand [`backend/scripts/smoke_test.py`](../backend/scripts/smoke_test.py) past `GET /health`: reject unauthenticated enrich; run a tiny authenticated `/enrich/sync`; exit non-zero on failure. Wire `make smoke` once the Makefile exists.
- [ ] **DEVPLAN (gap 82)** — This file. Keep phases updated when milestones land; do not treat presence of the file as “project complete.”
- [ ] **Fresh-setup verification (gap 84)** — After Makefile + smoke land: on a clean machine/worktree run `make setup` → `make up` → `make smoke` and record evidence (commands, dates, pass/fail). Blocked until 1/79 and 77 exist.

**Exit:** A new contributor can follow docs-only commands and get a green smoke without tribal knowledge.

---

## Phase 2 — Enricher correctness (guide 28, 31, 39, 64)

Close partial integrations called out in the guide audit and Architecture “open questions.”

- [ ] **Email pattern fallback (gap 28)** — Move beyond `{username}@{domain}` only; cover common corporate patterns where email-sleuth input allows.
- [ ] **Reacher order + catch-all (gap 31)** — SMTP mode: Reacher first; AfterShip only on miss/unknown; parse catch-all (`misc.is_catch_all` or equivalent) and surface low-trust / non-deliverable-strong status. Tests must prove order and catch-all behavior.
- [ ] **JobSpy boards (gap 39)** — Expand beyond Indeed + LinkedIn toward Glassdoor / Google Jobs / ZipRecruiter (or document an explicit, intentional subset with guide buy-in).
- [x] **GitHub throttle around gitrecon (gap 64)** — Code landed: `app/enrichers/gitrecon.py` detects 403/429 stderr, Redis throttle + cooldown, soft-fail empty fragment; config + `.env.example` keys; `tests/test_gitrecon_throttle.py`. Operator matrix doc: Phase 3 appendix in `backend/docs/LEGAL.md`.

**Exit:** Tier 3/4 enrichers match guide contracts under missing tools, rate limits, and catch-all SMTP without crashing the pipeline.

---

## Phase 3 — Compliance docs & source limits (guide 61, 64 matrix)

- [ ] **LinkedIn scraping section in LEGAL (gap 61)** — Document in [`backend/docs/LEGAL.md`](../backend/docs/LEGAL.md): public photo only, customer-supplied URL, no bulk scrape, Multilogin/session, ToS/rate-limit risk, `ENABLE_TIER1` gate. Link from operator docs; do not duplicate Architecture.
- [x] **Source-limit matrix (extends gap 64)** — [`backend/docs/LEGAL.md`](../backend/docs/LEGAL.md) appendix *Upstream source limits* covers LinkedIn/Multilogin, gitrecon/GitHub, SMTP/Reacher, Hyrepath ingress, and GitHub REST 5k/hr; cross-linked from `backend/docs/ARCHITECTURE.md` production section.

**Exit:** Legal/ops reviewers can answer “what’s allowed and what’s throttled” from docs alone.

---

## Phase 4 — Observability, signals, hardening (guide 68, 71)

- [ ] **Compose healthchecks completeness (gap 68)** — Ensure redis and remaining infra services that the API/worker depend on are gated; keep free-default vs profiled paid services clear.
- [ ] **Change signals product flow (gap 71)** — Today `POST /api/signals/changedetection` accepts/logs. Still open: watch → detect → notify product flow beyond webhook logging (storage, alerting, or customer-visible signal surface). **Do not mark 71 done for logging-only.**

**Exit:** Stack readiness is measurable; change signals are a product path, not only an ingest log line.

---

## Phase 5 — QA depth (guide 76, 78)

- [ ] **Real canary set (gap 76)** — Replace placeholder/example-only 20-entry sets with a maintained canary (technical / non-technical / private) and a runner that records pass/fail. Example JSON under `backend/docs/` is not sufficient.
- [ ] **Full-path E2E (gap 78)** — Harness: `make e2e-full-path` / `python backend/scripts/e2e_full_path_runner.py --ci`. Evidence: `backend/docs/e2e-evidence/2026-07-16-full-path-ci.md`. **Green CI run still required** (Docker socket access on verification host).

**Exit:** Releases can cite canary + full-path E2E evidence, not only shape tests and `/health`.

---

## Phase 6 — Production launch (guide 86–89)

All incomplete until there is evidence for **`enrich.hyrepath.io`** (or the agreed production host).

- [ ] **86** — Production deploy of API + worker + Postgres + Redis + required free sidecars
- [ ] **87** — Secrets, TLS, and env parity with staging (tokens, `DATABASE_URL`, `REDIS_URL`, R2 when used)
- [ ] **88** — Production acceptance: health/ready, authenticated enrich, opt-out/DSAR reachable without Bearer, smoke against prod base URL
- [ ] **89** — Ops runbook: rollback, audit purge cron, rate-limit/incident notes; link LEGAL product boundaries

**Exit:** Signed-off production acceptance checklist with URLs and dates — not “compose works locally.”

---

## Phase 7 — Guide completion gate (guide 90)

- [ ] **90 — Project complete under this Developer Guide** — Only after Phases 1–6 acceptance criteria are met on `main`, including gaps **71, 76, 78, 86–89**. Writing this DEVPLAN (82) does **not** complete 90.

**Exit:** Guide audit can mark task 90 complete with evidence links (PRs, canary runs, prod acceptance).

---

## Parallel workstreams (Wave trackers)

Track in-flight guide slices without claiming them done until merged:

| Guide # | Topic | Depends on | Status in this plan |
|---------|--------|------------|---------------------|
| 1 + 79 | Makefile | — | Phase 1 — open |
| 31 | Email verify order / catch-all | — | Phase 2 — open |
| 61 | LEGAL LinkedIn section | — | Phase 3 — open |
| 64 | gitrecon GitHub throttle + source-limit matrix | — | Phase 2 code done; Phase 3 matrix doc done |
| 77 | Expand smoke | — | Phase 1 — open |
| 82 | DEVPLAN.md | — | This file; keep checklist current |
| 84 | Fresh-setup verify | 1+79, 77 | Phase 1 — blocked |
| **71** | Signals watch/detect/notify | 70 (compose webhook) | Phase 4 — **open** |
| **76** | Real canary set | Example sets exist | Phase 5 — **open** |
| **78** | Full request→…→storage E2E | Split e2e scripts | Phase 5 — **open** |
| **86–89** | Prod host + acceptance | Phases 1–5 | Phase 6 — **open** |
| **90** | Guide complete | 71, 76, 78, 86–89 + DX | Phase 7 — **open** |

---

## Suggested merge / build order

1. Makefile (1+79) → expand smoke (77) → fresh-setup evidence (84)
2. Email catch-all (31), gitrecon throttle (64), LEGAL LinkedIn (61) — any order
3. JobSpy boards (39), email patterns (28), healthcheck gaps (68)
4. Signals product flow (71), real canary (76), full-path E2E (78)
5. Production 86–89 → only then consider 90

---

## Out of scope for this document

- Replacing Architecture, LEGAL, or README
- Claiming gaps **71, 76, 78, 86–90** complete
- Implementing Makefile, smoke, or LEGAL content here (owned by other tasks)

When Architecture Implementation status changes, update the matching Phase 0/2 checkboxes in the same PR when practical.
