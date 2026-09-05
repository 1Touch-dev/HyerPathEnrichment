# 0019. Tenancy model: `Brand` as a presentation-only concept

- **Status:** Accepted
- **Date:** 2026-08-26

## Context

Today, `backend/app/auth/models.py`'s `User` model has **no** `tenant_id`/`org_id`/`account_id`/
`agency_id` column, and this ADR does not introduce one. The only `account_id`-named column in
the schema (`OAuthAccount.account_id`) is Google's OAuth provider account id — a false positive,
not a tenancy concept.

The product is **not** pivoting to an isolated-tenant model. There is one internal operator/team
and one shared pool of candidates and recruiters. What's actually being introduced is `Brand`: a
presentation/marketing concept for running multiple branded storefronts (custom domain, chatbot
tone/branding, landing-page tier) on top of that one shared pool — not a per-agency data boundary.

This is squarely a "layer ownership" pattern change per `docs/adr/README.md`'s "When to add an
ADR" criteria (it decides, for the whole codebase, that presentation-layer branding must never be
conflated with an access-control boundary) — hence this ADR is mandatory, not optional.

## Decision

We chose a plain, unscoped `Brand` table with no access-scoping column anywhere **over** an
isolated-tenant model with an `org_id`/`brand_id` access-scoping column and JWT claim, for the
following reasons:

1. **`Brand` is a normal, unscoped table — not a tenancy mechanism, and not schema-per-tenant or
   database-per-tenant.** `Brand` is one plain table (`id`, `name`, `slug`, `custom_domain`,
   `chatbot_config`, landing-page-tier config, `is_active`, timestamps), with no FK from any
   business table back to it except the two presentation-only columns named below. Justified
   against: (a) the repo runs a single shared Postgres instance per deployment (ADR 0002 — SQLite
   local, Postgres Docker/prod) with no per-tenant provisioning automation, so schema-per-tenant or
   database-per-tenant would require net-new infra this repo has no precedent for, and there is no
   product requirement (single shared pool) that would justify that cost even if the infra
   existed; (b) a normal table keeps `Brand` reviewable and extensible (add a column, no
   migration-shaped ceremony) the same way any other reference table in this codebase is; (c) we
   explicitly reject column-based row-level tenancy (a `brand_id`/`org_id` FK used as a `WHERE`
   filter on shared tables) as unnecessary complexity for a product with no cross-brand isolation
   requirement — adding that filter pattern here would be solving a problem the product does not
   have, at the cost of every future query needing to remember a filter that protects nothing.
2. **No access-scoping column on `users`, and no JWT claim for brand/org — instead of** adding
   either. `users` gets no `org_id`/`brand_id` column at all, and no new JWT claim is added. Since
   any recruiter can already work any candidate in the shared pool, there is no access decision
   left for a claim or column to gate — adding one would be dead weight that invites a future
   engineer to (incorrectly) start using it as a filter, reintroducing the isolated-tenant model
   this ADR rejects. See `task-orchestration/machine-1-tenancy-core/03-auth-org-id-claim.md` (kept
   as a stub, not deleted, since other planning files in that doc set reference it by name) for the
   explicit "superseded" note.
3. **`users.signup_brand_id` is nullable, presentation-only, and never a query filter — instead of**
   a tenancy-scoping FK. The real column lives on `users` (the table backing candidate accounts —
   there is no separate `candidates` table in the current schema; "candidates" here means user rows
   without the recruiter/staff role), added as `signup_brand_id`, nullable FK to `brands.id`,
   `ondelete="SET NULL"`. It records which storefront a candidate signed up through for
   attribution/reporting and for per-brand chatbot tone — nothing reads it to decide what that
   candidate can see or who can see them. Nullable because most existing/legacy candidates signed
   up before any brand concept existed and have no storefront to attribute.
4. **`recruiter_candidate_assignments` is an ownership marker, not an access grant — instead of**
   an authorization table. A plain many-to-many table (`recruiter_user_id`, `candidate_user_id`,
   both FK to `users.id`) with no uniqueness constraint stronger than the pair itself, and no code
   path anywhere that uses its presence/absence to allow or deny a recruiter's ability to search,
   view, or act on a candidate. The business need it serves is "which candidates does recruiter X
   consider their own, for 'my assigned candidates' views and reporting" — a responsibility marker
   — not "which candidates is recruiter X permitted to touch." Any recruiter can act on any
   candidate whether or not an assignment row exists; this table is read by dashboards/filters,
   never by an authorization check.
5. **Per-brand-domain CORS stays an in-place `CORSMiddleware` retrofit, not a new proxy/gateway
   layer — instead of** introducing a reverse-proxy/gateway. Justified against
   `backend/docker/docker-compose.yml` having no reverse proxy container today — introducing one
   (e.g. Traefik/Nginx for per-domain routing) is out of scope for this ADR; the existing single
   FastAPI `CORSMiddleware` is extended in-place (`backend/app/main.py`) to include active brands'
   custom domains, exactly as before, just keyed off `Brand.custom_domain` instead of an
   `Organization.custom_origin`-shaped column.

### Confirmed by leadership (2026-08-26)

James was asked directly whether interface #1 of his original 4-interface list ("for Clients — AI
Placement Agency") meant other businesses running their own isolated placement agency on top of
this platform (real multi-tenant reselling — a paying business customer with its own staff,
users, clients, private candidate pool, branding, complete isolation, etc., which would directly
contradict the Decision section above), or a candidate-facing storefront framing the existing
`Brand` model already covers. His answer, quoted verbatim: **"No one should be able to run there
own staff users clients private candidate pool branding complete isolations etc — #1 refers to
the candidate facing user panel."** He also clarified interfaces #1/#2 are both candidate-facing
panels where AI does the placement — one for real jobs, one for freelance work: **"User has panel
that is client facing. Ai does placement on user panel for real job"** / **"user panel client
facing with ai being placement agency's, focusing on freelancers."**

This directly confirms the Decision section above — `Brand` as a presentation-only concept, no
per-agency tenant, no `org_id`/isolation boundary, one shared candidate/recruiter pool — is
correct as designed. **No rework of this ADR's Decision results from this answer.** See
`task-orchestration/README.md`'s "Confirmed by leadership" section (item 7) for the
traceability-index entry, and that same file's cross-reference note tying interfaces #1/#2 to
`post-tenancy-features/05-freelance-bidding-system.md` (freelance track) and to Machine 2's
existing recruiter-apply/resume-tailoring chunks (`09`/`10` — the "real jobs" placement workflow)
— neither interface requires new architecture beyond what this ADR and those chunks already spec.

## Tradeoffs

- Rejecting row-level brand/org filtering means this ADR is making a hard, explicit product bet:
  if a genuine data-isolation requirement ever emerges (e.g. a real third-party agency needing its
  own walled-off pool), that is a *new* ADR and a *new* schema change, not something this design
  degrades gracefully into. A future reader should not assume isolation was quietly half-built.
- `signup_brand_id` and `recruiter_candidate_assignments` existing in the schema creates a
  standing temptation for a future engineer to add a `WHERE` filter on them "just to scope things
  a bit." This ADR's Decision §2-4 is the citable reason that's wrong for this product, the same
  way this file's own conventions expect settled decisions to prevent re-litigation.
- No JWT claim for brand keeps every existing token shape unchanged (no additive claim, no
  staleness window to reason about) — pure upside relative to the isolated-tenant model's original
  `org_id`-claim design, which this ADR replaces.

## Consequences

- `backend/app/modules/brands/models.py` (new `Brand` model, `docs/adr/0019-tenancy-model.md`'s
  companion implementation chunk)
- `backend/app/auth/models.py` (`User` gets no new access-scoping column; `signup_brand_id` lives
  here instead, presentation-only)
- `backend/app/main.py` (CORS middleware retrofit, keyed off `Brand.custom_domain`)
- Forward-reference: the per-brand chatbot config feature reads `signup_brand_id` for a UX purpose
  (chatbot tone), and the recruiter-candidate assignment feature reads
  `recruiter_candidate_assignments` for "my assigned candidates" views.
