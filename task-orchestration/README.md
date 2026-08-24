# Task Orchestration — Placement-Agency Platform

Planning docs for pivoting HyrePath from a single-tenant candidate-enrichment backend into a
**single-operator, multi-brand placement platform**: one internal team works one shared pool of
candidates and recruiters, presented to the outside world through multiple branded storefronts
(`Brand`). A `Brand` is a marketing/presentation concept only — name, slug, optional custom
domain, chatbot config, landing-page tier config — **never** a data-isolation boundary. There is
no per-agency tenant, no `org_id` access-scoping column or JWT claim anywhere in this design, and
any recruiter can search, view, and act on any candidate in the shared pool regardless of which
brand storefront that candidate signed up through.

This directory is **documentation only**. No application code is changed by these files
themselves; each `.md` is a self-contained spec for a later implementation PR.

Base branch for this planning work: `master-complete-foundation` (HEAD at time of writing:
`142b3756`, "Merge pull request #248 ... admin-module3-4-cors-ratelimit"). Working branch:
`feat/placement-agency-platform`.

## Why this structure

Two machines/agents work in parallel from day one:

- **Machine 1** owns `machine-1-tenancy-core/` — the foundational, blocking work: what a
  `Brand` is, how it's stored, how CORS/presentation resolve per brand. Every chunk elsewhere in
  this doc set that reads `Brand`/`users.signup_brand_id`/`recruiter_candidate_assignments`
  eventually depends on this landing, so it is deliberately small and merges first. Unlike the
  original isolated-tenant design, this track adds **no access-control mechanism at all** — no
  `org_id` column, no JWT claim, no query filter — so it hands off no "add a WHERE clause" wave
  to anything downstream.
- **Machine 2** owns `machine-2-parallel-tracks/` — twelve independent feature tracks that do
  **not** touch brand/tenant scoping (because there is none to touch) and do not depend on
  `machine-1` landing first except where a specific chunk's own "Depends on" section says
  otherwise (see the dependency graph below). They can be built, reviewed, and merged largely in
  any order, concurrently with `machine-1`.

Once `machine-1-tenancy-core` merges to `master-complete-foundation`, only one further wave
remains:

- **`post-tenancy-features/`** — net-new features that build on the `Brand` model once it exists:
  candidate-level billing (freemium paywall) and brand landing/tier pages. There is no
  `post-tenancy-retrofit/` wave in this doc set — that wave existed only under the old
  isolated-agency-tenant model to backfill `org_id` scoping into pre-existing queries; since
  `Brand` never gates data access, there is nothing for such a wave to retrofit, and it has been
  deleted outright. There is also no "hard gate" of any kind blocking these features — they only
  need `Brand` to exist as a table, not a passing isolation-test suite (none exists, none is
  needed).

## Dependency graph

```mermaid
graph TD
  M1_00[m1 00 overview]
  M1_01[m1 01 adr tenancy model]
  M1_02[m1 02 schema and migration]
  M1_03[m1 03 auth org id claim - superseded stub]
  M1_05[m1 05 staff invite flow]
  M1_04[m1 04 cors retrofit, per-brand domain]
  M1_06[m1 06 outbound ip strategy - deferred decision record]

  M2_00[m2 00 overview]
  M2_01[m2 01 progressive profiling fields]
  M2_02[m2 02 country demand intelligence]
  M2_03[m2 03 outreach strategy dimension]
  M2_04[m2 04 rbac admin platform]
  M2_05[m2 05 outreach canspam send compliance]
  M2_06[m2 06 linkedin outreach send]
  M2_07[m2 07 demand intelligence resume integration]
  M2_08[m2 08 recruiter candidate assignment]
  M2_09[m2 09 recruiter apply and suggest]
  M2_10[m2 10 resume tailoring]
  M2_11[m2 11 per-brand chatbot config]
  M2_12[m2 12 linkedin sourcing intern multilogin]

  PTF_01[ptf 01 billing stripe integration]
  PTF_02[ptf 02 brand landing pages]
  PTF_03[ptf 03 brand deactivation]

  M1_00 --> M1_01 --> M1_02 --> M1_05 --> M1_04
  M1_03 -.->|superseded stub, no code, not on critical path| M1_02
  M1_04 -.->|domain-routing precedent cited by 06's interpretation B| M1_06
  M2_05 -.->|real-sending-infra gap cited by 06's interpretation A| M1_06

  M1_02 -->|Brand model| PTF_01
  M1_02 -->|Brand model| PTF_02
  M1_02 -->|Brand.is_active| PTF_03
  M1_02 -->|Brand + users.signup_brand_id| M2_08
  M1_02 -->|Brand + users.signup_brand_id| M2_11

  M2_00 --> M2_01
  M2_00 --> M2_02
  M2_00 --> M2_03
  M2_00 --> M2_04
  M2_03 --> M2_05
  M2_05 --> M2_06
  M2_02 --> M2_07
  M2_03 --> M2_07
  M2_02 --> M2_10
  M2_08 -.->|conceptual only, no structural dependency| M2_09
  M2_06 -.->|leads feed 06's queue as input, no code dependency| M2_12
```

`machine-2-*` nodes have **no edges into `machine-1-*`** except where a chunk's own file states a
real schema dependency — `08-recruiter-candidate-assignment.md` and
`11-per-brand-chatbot-config.md` are the two genuine exceptions, since both read columns/tables
`machine-1/02` creates (`users.signup_brand_id`, and the design premise that
`recruiter_candidate_assignments` is an ownership marker on a single shared pool). Every other
machine-2 chunk, including `04-rbac-admin-platform.md`, needs nothing from `machine-1` to land
first: `04` extends the *existing* `roles`/`permissions` tables (already shipped, ADR 0015) with
this platform's own internal-team role rows (`team_owner`, `recruiter`) — it does not require
`Brand` or any brand/org column to exist to insert a `Role` row, and — unlike the old
`agency_owner`/`agency_recruiter` design — it never becomes tenant-aware later, because there is
no tenant to become aware of.

`03-auth-org-id-claim.md` is drawn as a dashed, non-blocking edge because it is a **superseded
stub, not active work**: its original scope (an `org_id` JWT claim, an `OrgScopedUser` dependency)
is not implemented. It is kept as a file, not deleted, only because other files in this doc set
still reference it by name; it produces no code and sits on no critical path. The implementation
order that matters within `machine-1` is **`01 → 02 → 05 → 04`** — `03` is irrelevant to that
order.

`M2_07`'s two incoming edges (`M2_02 --> M2_07`, `M2_03 --> M2_07`) mirror that chunk's own
"Depends on" section exactly: it needs `M2_02`'s `get_top_countries_for_role()` function and
`M2_03`'s established LLM prompt-construction append-pattern (`_STRATEGY_INSTRUCTIONS`'s
composition style) as the convention its own prompt-context addition follows. Per that chunk's
own ground-truth note, its actual data dependency (`desired_roles` on `CVData`) already exists
independent of `machine-2-parallel-tracks/01-progressive-profiling-fields.md`, so there is
deliberately **no** `M2_01 --> M2_07` edge.

`M2_09`'s edge to `M2_08` is drawn dashed/conceptual because `09`'s own file is explicit that its
authorization does **not** check `RecruiterCandidateAssignment` at all — any recruiter may
apply/suggest on behalf of any candidate, consistent with `08`'s "assignment is not an access
gate" decision. The two chunks are thematically related (both are recruiter-on-behalf-of-candidate
actions) but have no structural/import dependency; `09` can be implemented and merged before,
after, or in parallel with `08`.

`M2_12`'s edge to `M2_06` is drawn dashed for the same reason: `12` (sourcing/scouting leads) is
explicitly **not** wired into `06`'s (send task-queue) tables — a `SourcedCandidateLead` is an
*input* a recruiter may later choose to act on via `06`'s existing flow, using the lead's
`linkedin_profile_url`, but no code in `12` calls into or depends on `06`'s modules, and no code
in `06` depends on `12`. Both chunks also carry their own prominent, independent legal-risk
sections (see "LinkedIn legal-risk chunks" below) — read both before implementing either.

`M2_02 --> M2_10` is a new edge (added alongside chunk `M1_06`, below): `10-resume-tailoring.md`'s
"Demand-intelligence context injection" section reads `M2_02`'s `get_top_countries_for_role()`,
closing a dangling promise `02-country-demand-intelligence.md` had made (its own "future consumer"
note named `10` without `10` ever actually depending on `02`). This mirrors the existing
`M2_02 --> M2_07` edge exactly — same function, same read-only import, same flag-gated/additive
contract — applied to the resume-tailoring prompt instead of the outreach-drafting prompt.

`M1_06` (`machine-1-tenancy-core/06-outbound-ip-strategy-deferred.md`) is a new chunk: an explicit
decision record, not implementation work, resolving the "multiple outbound IPs" ambiguity from
the original task brief as an intentional deferral rather than a silent gap. Its two dashed
incoming edges are citation-only, not code dependencies — it reads `M2_05`'s "no real
outreach-sending infrastructure exists yet" ground truth (for its interpretation (A), dedicated
sending IPs) and `M1_04`'s `Brand.custom_domain`/CORS-resolution design (for its interpretation
(B), per-brand hosting isolation, which it concludes is already fully handled by `M1_04`'s
existing design). `M1_06` produces no code and blocks nothing else in this doc set — it exists
purely so a future reader finds a reasoned "defer, here's why, here's the trigger to revisit"
record instead of silence.

`PTF_03` (brand deactivation) has **no edge to `PTF_01`** (billing) — this is a deliberate
absence, not an oversight. The prior "org offboarding" design depended on billing for
Stripe-customer-redaction sequencing because deleting an *organization* cascaded through its
owned users' financial records. Deactivating a `Brand` cascades through nothing (a brand never
owned candidates), so there is no billing interaction to sequence against at all.

## Merge order

1. **Anytime, any order, fully parallel:** `machine-2-parallel-tracks/01`, `02`, `04`, and `08`
   may be implemented and merged to `master-complete-foundation` independently of everything else
   in this document (each touches disjoint files — see each file's "Do not touch" list). Two soft
   ordering preferences, neither a hard block: `07` (demand-intelligence resume integration) reuses
   `02`'s read function and `03`'s prompt-append convention, so implement `07` after both; `09`
   (recruiter apply/suggest) is conceptually related to `08` but has no structural dependency on
   it, so it may land in any order relative to `08`.
2. **Sequential sub-chain, parallel to everything else in step 1:** `03 → 05 → 06`
   (outreach strategy dimension → CAN-SPAM compliance → LinkedIn send) — each later chunk imports
   the previous chunk's schema/service additions, so these three are one branch or three stacked
   branches, implemented and reviewed in that order.
3. **Must merge before any chunk that reads `Brand`/`users.signup_brand_id` (namely
   `machine-2-parallel-tracks/08`, `11`, and all of `post-tenancy-features/`):**
   `machine-1-tenancy-core`, in its internal chunk order **`01 → 02 → 05 → 04`**. `03` is a
   superseded stub and is not part of this sequential chain — it can be left exactly as-is,
   merged or not, with zero effect on anything else in this doc set. Chunk `05` (staff invite
   flow) sits directly after `02` and before `04` — `05` needs `02`'s schema to exist (its
   `invited_by`/role-assignment plumbing) but has no dependency on `04`'s CORS retrofit at all, and
   placing invite-creation ahead of the CORS retrofit is the more sensible product-readiness
   order (staff can be invited before the per-brand-domain CORS allow-list is wired up). This is
   one branch, `feat/tenancy-core`, reviewed as up to four stacked PRs (or one PR, implementer's
   choice) covering `01`, `02`, `05`, `04` — `03` needs no PR at all since it is a no-op stub.
   **Note:** `08` and `11` do not strictly need to *wait* for this step if their own migrations
   target the real current Alembic head instead of assuming `machine-1/02`'s specific revision —
   but neither can be considered functionally complete (their own FK/column reads will fail) until
   `machine-1/02`'s schema is actually present, so treat this as a soft-but-strong ordering
   preference for `08`/`11` specifically, distinct from the hard block on `post-tenancy-features/*`
   below.
4. **After `machine-1-tenancy-core` merges:** `post-tenancy-features/01` (billing), `02` (brand
   landing pages), and `03` (brand deactivation) may branch and merge in any order relative to
   each other — unlike the pre-pivot design, `03` has **no** dependency on `01` (deactivation has
   no billing interaction at all, since billing is candidate-level, not brand-level; see the
   dependency-graph note above). There is no isolation-test hard gate of any kind blocking this
   step — that gate existed only for the now-deleted `post-tenancy-retrofit/` wave.
5. **Independent of every step above, at any time:** `machine-2-parallel-tracks/10` (resume
   tailoring) and `12` (LinkedIn sourcing) have no schema/migration dependency on any other chunk
   in this doc set (`10` adds no migration at all — its own "Demand-intelligence context
   injection" section only reads `M2_02`'s existing read function, no schema coupling; `12`
   depends only on the existing RBAC `require_permission` mechanism, seeding its own permission
   row directly if `04` hasn't landed yet). Both may be dispatched and merged whenever convenient.
   `machine-1-tenancy-core/06-outbound-ip-strategy-deferred.md` is also independent of the `01 →
   02 → 05 → 04` chain and of every other chunk's merge status — it is a documentation-only
   decision record with no code and no schema, so it can be merged at any time and blocks nothing.

## LinkedIn legal-risk chunks

Two chunks in this doc set — `machine-2-parallel-tracks/06-linkedin-outreach-send.md` (outbound
send) and `machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md` (inbound
sourcing/scouting) — each carry their own prominent, independently-required legal-risk section at
the top of the file. Both are deliberately human-in-the-loop, not automated: `06` is a task queue
where a human operator performs the actual LinkedIn send in their own session; `12` is a manual
data-entry form where an intern types in what they personally observed on a profile, with zero
programmatic reads of linkedin.com anywhere in the design. `12`'s fact pattern is, if anything,
closer to the actual `hiQ Labs v. LinkedIn` judgment (data scraping) than `06`'s is — read both
risk sections before implementing either, and do not treat either file's "human-in-the-loop"
framing as decoration; it is the load-bearing legal-risk mitigation for both chunks.

## Subagent role assignment

| Track | Developer | Reviewer | Tester | Notes |
|---|---|---|---|---|
| `machine-1-tenancy-core` (`01`, `02`, `05`, `04`) | 1 developer subagent, sequential dispatch (chunk N waits for chunk N-1's schema to exist; order is `01→02→05→04`) | 1 reviewer subagent per chunk, gates progression to next chunk | 1 tester subagent after chunk `04`, full CORS+invite-flow test pass | `03` is a superseded stub — no subagent dispatch of any kind; it is not implemented |
| `machine-1-tenancy-core/06` | No developer subagent — this chunk is a decision record, not code; the file itself is the deliverable | 1 reviewer subagent confirms the file is linked from this README's dependency graph/gap-tracking section and that no other chunk contradicts its deferral decision | No tester subagent — nothing to test, see this chunk's own "Verification" (a documentation checklist) | Independent of the `01→02→05→04` chain; may be dispatched/merged whenever convenient (see "Merge order" §5) |
| `machine-2-parallel-tracks/01, 02, 04, 08` | 1 developer subagent per track, dispatched in parallel | 1 reviewer subagent per track | 1 tester subagent per track | Independent CV/profiling, JobSpy-country, RBAC, and recruiter-assignment domains, zero file overlap |
| `machine-2-parallel-tracks/03 → 05 → 06` | 1 developer subagent, sequential within this sub-chain (`06` imports the schema `03` defines and the compliance primitives `05` defines) | 1 reviewer subagent per chunk — `06`'s reviewer must also confirm the human-in-the-loop design boundary (no LinkedIn network call/browser automation anywhere in the diff) | 1 tester subagent after `06` | This sub-chain is internally sequential even though the whole `machine-2` track is parallel to `machine-1` |
| `machine-2-parallel-tracks/07` | 1 developer subagent, dispatched after `02` and `03` (code-import dependency, not a schema one — see "Merge order" §1) | 1 reviewer subagent, byte-identical-when-disabled regression check is release-blocking | 1 tester subagent | Small, additive prompt-context chunk — no new table, no new migration |
| `machine-2-parallel-tracks/09` | 1 developer subagent, may be dispatched any time relative to `08` (conceptual, not structural, dependency) | 1 reviewer subagent, must confirm `RecruiterCandidateAssignment` is never read for authorization | 1 tester subagent | Adds `users.recruiter_action_mode`; default `approval_required` is release-blocking to verify |
| `machine-2-parallel-tracks/10` | 1 developer subagent, fully independent | 1 reviewer subagent, must confirm zero new tables/migrations/columns anywhere in the diff | 1 tester subagent — owns the no-persistence regression test | Ephemeral RQ-result-TTL design; the "nothing is ever persisted" invariant is the release-blocking review item |
| `machine-2-parallel-tracks/11` | 1 developer subagent, dispatched after `machine-1/02` lands (needs `Brand`/`users.signup_brand_id`) | 1 reviewer subagent, must confirm the no-brand and `chatbot_config IS NULL` cases both produce byte-identical default prompts | 1 tester subagent | Extends `CvChatService`/`build_chat_system_prompt` in place; no new router/schema surface |
| `machine-2-parallel-tracks/12` | 1 developer subagent, fully independent (seeds its own permission row if `04` hasn't landed) | 1 reviewer subagent — **release-blocking**: must confirm zero network calls to `linkedin.com`/browser automation anywhere in the diff, identical bar to `06`'s reviewer | 1 tester subagent | Manual lead-entry form only; see "LinkedIn legal-risk chunks" above |
| `post-tenancy-features/01, 02` | 1 developer subagent per track, dispatched after `machine-1-tenancy-core` merges, parallel to each other | 1 reviewer subagent per track — `01`'s reviewer additionally confirms the server-side (never UI-only) blur/teaser paywall requirement | 1 tester subagent per track | No hard gate beyond `Brand` existing — the old isolation-test gate no longer applies |
| `post-tenancy-features/03` | 1 developer subagent, dispatched after `machine-1-tenancy-core` merges — **no** dependency on `01` | 1 reviewer subagent, confirms zero candidate/recruiter/document/job-match/outreach rows are touched by deactivation (regression-blocking) | 1 tester subagent | Reuses existing admin audit logging; no new tombstone table, no grace period, fully reversible |

## Branch naming convention

- `feat/tenancy-core` — machine-1, chunks `01`, `02`, `05`, `04` (`03` needs no branch — it is a
  superseded stub with no implementation)
- `feat/progressive-profiling-fields`, `feat/country-demand-intelligence`,
  `feat/outreach-strategy-dimension`, `feat/rbac-admin-platform`,
  `feat/outreach-canspam-compliance`, `feat/linkedin-outreach-send`,
  `feat/demand-intelligence-resume-integration`, `feat/recruiter-candidate-assignment`,
  `feat/recruiter-apply-and-suggest`, `feat/resume-tailoring`, `feat/per-brand-chatbot-config`,
  `feat/linkedin-sourcing-intern-multilogin` — machine-2, one branch per track (the `03 → 05 → 06`
  sub-chain may be three stacked branches or three commits on one branch, implementer's choice, as
  long as each is reviewable independently)
- `feat/billing-stripe`, `feat/brand-landing-pages`, `feat/brand-deactivation` —
  post-tenancy-features

All branches target `master-complete-foundation` directly (this repo does not use a long-lived
`develop` branch). Per the repo's git workflow rule, no branch listed here is merged by the
implementing agent — each opens a PR and stops for human review.

## Assumptions this README makes (flag if wrong)

- `docs/adr/0018-tenancy-model.md` (or whatever number it actually lands as — see
  `machine-1-tenancy-core/01-adr-0015-tenancy-model.md`'s own "Naming" note; the repo's real ADR
  index already runs through `0017` as of 2026-08-22) is the single source of truth for the
  `Brand`/access-control decision. If a future reader finds `org_id`, `tenant_id`, or
  `Organization` anywhere in application code, that is drift from this doc set's decision, not a
  feature to build against.
- A `User` row backs both candidates and staff (recruiters/interns/`team_owner`) — there is no
  separate `candidates` table anywhere in this schema. Every chunk in this doc set that informally
  says "candidate" means "a `users` row without a staff/recruiter role."
- `job_matching`/`outreach`/`documents`/`portfolio`/`admin` queries are, and remain, entirely
  unscoped by brand — no chunk in this doc set adds a `WHERE` clause filtering any of those tables
  by `signup_brand_id` or any brand-derived value. If a future chunk proposes such a filter citing
  this doc set, that is a misreading of every "Do not touch"/"Ambiguities resolved" section that
  explicitly rejects it (see `machine-1-tenancy-core/00-overview.md`,
  `machine-2-parallel-tracks/08-recruiter-candidate-assignment.md`, and
  `post-tenancy-features/02-brand-landing-pages.md` in particular).

## Gaps closed since initial planning (2026-08-22, brand-model pivot)

A later pass on this doc set replaced the isolated-agency-tenant model with the single-operator,
multi-brand model described above, and closed several gaps surfaced along the way. This section
is the traceability index for anyone auditing the doc set later.

| # | Gap | Closed by |
|---|-----|-----------|
| 1 | Original design isolated agencies as tenants with `org_id`-scoped data — did not match the actual product (one internal team, one shared pool, branded storefronts) | `docs/adr/0018-tenancy-model.md` (via `machine-1-tenancy-core/01`) + full `machine-1-tenancy-core/00`, `02`, `03`, `04`, `05` rewrite |
| 2 | Cross-tenant isolation retrofit wave (`post-tenancy-retrofit/`) no longer had a purpose once there is no tenant boundary | All four `post-tenancy-retrofit/*.md` files deleted |
| 3 | Billing was org/seat-level (`OrganizationSubscription`) — did not match candidate-level freemium product reality | `post-tenancy-features/01-billing-stripe-integration.md` rewritten around `UserSubscription` + server-side blurred-preview paywall |
| 4 | No recruiter-to-candidate ownership/workload marker existed | `machine-2-parallel-tracks/08-recruiter-candidate-assignment.md` (new chunk) — explicitly an ownership marker, never an access gate |
| 5 | No way for a recruiter to apply/suggest on a candidate's behalf | `machine-2-parallel-tracks/09-recruiter-initiated-apply-and-suggest.md` (new chunk) — gated by a candidate-facing autonomous-vs-approval preference |
| 6 | No per-company resume personalization existed | `machine-2-parallel-tracks/10-resume-tailoring.md` (new chunk) — ephemeral, RQ-result-TTL-backed, no new persisted document type |
| 7 | `Brand.chatbot_config` (reserved by `machine-1/02`) had no consumer | `machine-2-parallel-tracks/11-per-brand-chatbot-config.md` (new chunk) — extends `CvChatService`'s system prompt |
| 8 | No LinkedIn sourcing/scouting workflow existed (only outbound send, chunk `06`) | `machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md` (new chunk) — manual lead-entry form, its own prominent legal-risk section |
| 9 | `06-linkedin-outreach-send.md` misattributed the `hiQ Labs v. LinkedIn` $500,000 judgment to automated *messaging* | Corrected in place — the judgment rests on data scraping/fake-account claims, not messaging; `12`'s new legal-risk section is written consistently with the corrected citation |
| 10 | Country-demand data (`02`) had no tiering methodology for recruiter prioritization | `machine-2-parallel-tracks/02-country-demand-intelligence.md` extended with the Tier 1/2/3 market-research methodology and India/Middle East resume-personalization notes |
| 11 | `learning_style`/`prep_timeline_weeks` (from `01`) were collected but never used | `machine-2-parallel-tracks/01-progressive-profiling-fields.md` extended with the learning-style-suggestion-back feature |
| 12 | Outreach drafting had no employer-tier or role-type/seniority variation | `machine-2-parallel-tracks/03-outreach-strategy-dimension.md` extended with `EmployerCompanyTier` (manual) and role-type/seniority prompt variation |
| 13 | RBAC system roles (`agency_owner`/`agency_recruiter`) implied per-tenant agency accounts | `machine-2-parallel-tracks/04-rbac-admin-platform.md` renamed to `team_owner`/`recruiter`, reflecting one internal team |
| 14 | "Org offboarding and deletion" (`post-tenancy-features/03`) staged a full cascading-deletion pipeline that assumed organizations owned user data | Shrunk to `post-tenancy-features/03-org-offboarding-and-deletion.md`'s current scope: reversible brand deactivation only, no cascade, no grace period, no Stripe redaction |
| 15 | Brand landing pages (`post-tenancy-features/02`) had no tier/segment variant | Extended with `/b/{slug}/{tier}` sub-pages, backed by `Brand.landing_page_tier_config` |
| 16 | `03-outreach-strategy-dimension.md` deferred wiring `EmployerCompanyTier` into the LLM drafting prompt, leaving a manual, human-set field with no actual effect on drafting output | `machine-2-parallel-tracks/03-outreach-strategy-dimension.md`'s new "Company-tier-driven drafting variation" section — flag-gated (`enable_company_tier_in_outreach_drafting`, default `False`), byte-identical-when-disabled, human-review-before-broad-enable rollout |
| 17 | `02-country-demand-intelligence.md` named `10-resume-tailoring.md` as a "future consumer" of country-demand data, but `10`'s own dependency list never actually included `02` — a dangling promise | `machine-2-parallel-tracks/10-resume-tailoring.md`'s new "Demand-intelligence context injection" section (mirrors `07`'s `_demand_context_line` contract under a new `enable_demand_intelligence_in_resume_tailoring` flag) + `07-demand-intelligence-resume-integration.md`'s new cross-reference note pointing to it |
| 18 | The original task brief's "multiple different ips displaying account info or updates" phrase was ambiguous and had no documented resolution anywhere in this doc set | `machine-1-tenancy-core/06-outbound-ip-strategy-deferred.md` (new chunk) — an explicit decision record resolving both plausible interpretations (dedicated sending IPs; per-brand hosting isolation) as deferred, with concrete trigger conditions and citations, rather than a silent gap |
