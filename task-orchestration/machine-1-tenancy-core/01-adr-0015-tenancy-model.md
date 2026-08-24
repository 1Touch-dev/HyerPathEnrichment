# Machine 1, Chunk 1 — ADR: Tenancy Model

## Scope

Exactly one file to create:

- `docs/adr/0018-tenancy-model.md`

Exactly one file to edit:

- `docs/adr/README.md` — add one row to the Index table.

## Naming — read this before creating the file

The task brief that generated this planning doc set stated "next number is 0015 since 0001-0014
exist." That was true when that research was done, but **as of 2026-08-22 the repo's actual ADR
index already runs through `0017`** (`0015-admin-module-rbac-audit-mfa.md`,
`0016-phase2-moderation-review-queue.md`,
`0017-interview-practice-question-personalization-and-queue-isolation.md` are all merged to
`master-complete-foundation`). **Before creating this file, re-run:**

```bash
ls docs/adr/*.md | sort
```

and confirm `0018` is genuinely the next free number. If another ADR has landed between this
planning doc being written and this chunk being implemented, use whatever the next free number
actually is instead, and rename the file accordingly — do not silently use a taken number.

## File to create: `docs/adr/0018-tenancy-model.md`

Copy the structure of `docs/adr/template.md` exactly (Status/Date header, Context, Decision,
Tradeoffs, Consequences). Content requirements — the actual prose is the implementer's to write,
but it must cover all of the following decisions and cite the same ground-truth facts this
planning doc set was built from:

### Context section must state

- Today, `backend/app/auth/models.py`'s `User` model (line 18) has **no**
  `tenant_id`/`org_id`/`account_id`/`agency_id` column, and this ADR does not introduce one. The
  only `account_id`-named column in the schema (`OAuthAccount.account_id`, line 86) is Google's
  OAuth provider account id — a false positive, not a tenancy concept.
- The product is **not** pivoting to an isolated-tenant model. There is one internal
  operator/team and one shared pool of candidates and recruiters. What's actually being
  introduced is `Brand`: a presentation/marketing concept for running multiple branded
  storefronts (custom domain, chatbot tone/branding, landing-page tier) on top of that one shared
  pool — not a per-agency data boundary.
- This is squarely a "layer ownership" pattern change per `docs/adr/README.md`'s "When to add an
  ADR" criteria (it decides, for the whole codebase, that presentation-layer branding must never
  be conflated with an access-control boundary) — hence this ADR is mandatory, not optional.

### Decision section must choose and justify, explicitly

1. **`Brand` is a normal, unscoped table — not a tenancy mechanism, and not schema-per-tenant or
   database-per-tenant.** Decision: `Brand` is one plain table (`id`, `name`, `slug`,
   `custom_domain`, `chatbot_config`, landing-page-tier config, `is_active`, timestamps), with no
   FK from any business table back to it except the two presentation-only columns named below.
   Justify against: (a) the repo runs a single shared Postgres instance per deployment (ADR
   0002 — SQLite local, Postgres Docker/prod) with no per-tenant provisioning automation, so
   schema-per-tenant or database-per-tenant would require net-new infra this repo has no
   precedent for, and there is no product requirement (single shared pool) that would justify
   that cost even if the infra existed; (b) a normal table keeps `Brand` reviewable and
   extensible (add a column, no migration-shaped ceremony) the same way any other reference table
   in this codebase is; (c) explicitly reject column-based row-level tenancy (a `brand_id`/
   `org_id` FK used as a `WHERE` filter on shared tables) as unnecessary complexity for a product
   with no cross-brand isolation requirement — adding that filter pattern here would be solving a
   problem the product does not have, at the cost of every future query needing to remember a
   filter that protects nothing.
2. **No access-scoping column on `users`, and no JWT claim for brand/org.** Decision: `users` gets
   no `org_id`/`brand_id` column at all, and no new JWT claim is added. Justify: since any
   recruiter can already work any candidate in the shared pool, there is no access decision left
   for a claim or column to gate — adding one would be dead weight that invites a future engineer
   to (incorrectly) start using it as a filter, reintroducing the isolated-tenant model this ADR
   rejects. See `03-auth-org-id-claim.md` (kept as a stub, not deleted, since other planning
   files in this doc set reference it by name) for the explicit "superseded" note.
3. **`candidates.signup_brand_id` is nullable, presentation-only, and never a query filter.**
   Decision: the real column lives on `users` (the table backing candidate accounts — there is no
   separate `candidates` table in the current schema; "candidates" here means user rows without
   the recruiter/staff role), added as `signup_brand_id`, nullable FK to `brands.id`,
   `ondelete="SET NULL"`. Justify: it records which storefront a candidate signed up through for
   attribution/reporting and for `machine-2-parallel-tracks/11-per-brand-chatbot-config.md`'s
   per-brand chatbot tone — nothing reads it to decide what that candidate can see or who can see
   them. Nullable because most existing/legacy candidates signed up before any brand concept
   existed and have no storefront to attribute.
4. **`recruiter_candidate_assignments` is an ownership marker, not an access grant.** Decision: a
   plain many-to-many table (`recruiter_user_id`, `candidate_user_id`, both FK to `users.id`) with
   no uniqueness constraint stronger than the pair itself, and no code path anywhere that uses its
   presence/absence to allow or deny a recruiter's ability to search, view, or act on a candidate.
   Justify: the business need it serves is "which candidates does recruiter X consider their own,
   for 'my assigned candidates' views and reporting" — a responsibility marker — not "which
   candidates is recruiter X permitted to touch." Any recruiter can act on any candidate whether
   or not an assignment row exists; this table is read by dashboards/filters, never by an
   authorization check.
5. **Per-brand-domain CORS stays an in-place `CORSMiddleware` retrofit, not a new proxy/gateway
   layer.** Justify against `backend/docker/docker-compose.yml` having "no reverse proxy container"
   today — introducing one (e.g. Traefik/Nginx for per-domain routing) is out of scope for this
   ADR; the existing single FastAPI `CORSMiddleware` is extended in-place (chunk `04`) to include
   active brands' custom domains, exactly as before, just keyed off `Brand.custom_domain` instead
   of `Organization.custom_origin`.

### Tradeoffs section must include (at minimum)

- Rejecting row-level brand/org filtering means this ADR is making a hard, explicit product bet:
  if a genuine data-isolation requirement ever emerges (e.g. a real third-party agency needing
  its own walled-off pool), that is a *new* ADR and a *new* schema change, not something this
  design degrades gracefully into. Name this explicitly so a future reader doesn't assume
  isolation was quietly half-built.
- `signup_brand_id` and `recruiter_candidate_assignments` existing in the schema creates a
  standing temptation for a future engineer to add a `WHERE` filter on them "just to scope things
  a bit." This ADR's Decision §2-4 must be the citable reason that's wrong for this product, the
  same way `docs/adr/README.md`'s own conventions expect settled decisions to prevent re-litigation.
- No JWT claim for brand keeps every existing token shape unchanged (no additive claim, no
  staleness window to reason about) — pure upside relative to the isolated-tenant model's
  original `org_id`-claim design, which this ADR replaces.

### Consequences section must link

- `backend/app/modules/brands/models.py` (new `Brand` model, chunk `02`)
- `backend/app/auth/models.py` (`User` gets no new access-scoping column; `signup_brand_id` lives
  here instead, presentation-only)
- `backend/app/main.py` (CORS middleware retrofit, chunk `04`)
- Forward-reference `machine-2-parallel-tracks/11-per-brand-chatbot-config.md` as the feature that
  actually reads `signup_brand_id` for a UX purpose (chatbot tone), and
  `machine-2-parallel-tracks/08-recruiter-candidate-assignment.md` as the feature that reads
  `recruiter_candidate_assignments` for "my assigned candidates" views.

## File to edit: `docs/adr/README.md`

Add exactly one row to the **Index** table (after the existing `0017` row), following the exact
existing row format:

```markdown
| [0018](0018-tenancy-model.md) | Brand as a presentation-only concept; no cross-brand data isolation | Accepted | 2026-08-22 |
```

(Adjust the ADR number/filename/date if step "Naming" above found a different next-free number
at implementation time. Status starts as `Accepted` per this planning doc set's intent — this
is a settled decision for the effort, not a still-open discussion — but the implementer/reviewer
may downgrade it to `Proposed` if genuinely still under debate at implementation time.)

## Verification

Run `python backend/scripts/verify_adrs.py` after both edits — per `docs/adr/README.md`'s own
documented verification step. It checks ADR structure, the Accepted set, cross-links, and PR
template presence. This must pass before this chunk is considered done.

## Do not touch

- No code changes in this chunk — documentation only (the ADR file itself, plus the one README
  index row). Do not create the `Brand` model or migration here — that is chunk `02`.
- Do not edit any other row in `docs/adr/README.md`'s Index table.
- Do not touch `.github/pull_request_template.md` in this chunk.
