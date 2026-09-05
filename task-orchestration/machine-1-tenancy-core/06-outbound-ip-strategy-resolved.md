# Machine 1, Chunk 6 — Outbound IP Strategy: Resolved by Leadership (2026-08-24/25)

## Status: resolved — leadership answered the exact clarifying question directly

**This chunk was previously filed as `06-outbound-ip-strategy-deferred.md`, an explicit decision
record to defer both candidate interpretations of the original ambiguous "multiple different ips"
phrase.** That deferral is now superseded: James was asked the exact disambiguating question this
file's original two interpretations posed, and he answered both directly. This file is renamed
`06-outbound-ip-strategy-resolved.md` and rewritten accordingly — it is no longer a deferral
record, it is a resolution record. Every other file in this doc set that referenced the old
filename/status (`06-outbound-ip-strategy-deferred.md`, "deferred decision record") has been
updated to point at this file under its new name and status — see `README.md`'s dependency graph,
merge order, and gap-tracking sections.

## Depends on

- `machine-2-parallel-tracks/05-outreach-canspam-send-compliance.md` — for the real-sending-
  infrastructure gap this chunk's interpretation (A) below relies on (that chunk's own "Ground
  truth" section is the source for "no SMTP-sending pipeline exists for outreach today").
- `04-cors-and-ratelimit-retrofit.md` — for the domain-routing precedent this chunk's
  interpretation (B) below cites, and against which James's answer now creates real tension (see
  below).
- `machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md` — interpretation (A)'s
  resolution is now a cross-reference into that chunk's existing "Multilogin profile/account
  management" section, not a separate design here.

## The original ambiguity (for context — now resolved, not still open)

The original task brief that generated this doc set included the phrase "multiple different ips
displaying account info or updates," without further detail. Read literally, that admitted (at
least) two materially different interpretations:

- **(A) Email/LinkedIn-sending reputation protection** — the idea that outbound messages sent on
  behalf of different brands/accounts should originate from different IP addresses, for sender-
  reputation/deliverability reasons (dedicated IPs, IP warming).
- **(B) Per-brand hosting/network isolation** — the idea that each brand storefront should be
  served from a distinct IP address, for presentation/routing or perceived-isolation reasons.

James was asked to disambiguate directly, and answered both. Neither interpretation is
speculative or inferred below — both are now grounded in his literal words.

## Interpretation (A), resolved: Multilogin per-account IP diversity — already covered elsewhere

**James's words: "Multiple different ips, is to use multilogin in order to create multiple
users."** This resolves interpretation (A) as being about per-*account* IP/fingerprint diversity
for individually-owned automation accounts (e.g. LinkedIn sourcing/intern accounts), not about
dedicated sending IPs for outbound email/LinkedIn-message reputation protection in the sense this
file's original deferral record analyzed (SendGrid/Mailgun/Postmark dedicated-IP-volume
thresholds). Read literally, "multilogin in order to create multiple users" **is exactly**
`machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md`'s existing "Multilogin
profile/account management" section — one Multilogin browser profile (consistent
fingerprint/proxy, i.e. a distinct effective IP/identity) per one real, intern-owned LinkedIn
account, so each account behaves consistently session-to-session without looking like a new
device every time.

**Resolution: no new chunk, no new design here.** This does not need its own infrastructure
spec — it needs a cross-reference. `12`'s file already fully specs the Multilogin
profile-per-account model James is describing; the only gap was that this file's own decision
record didn't point back at it as the resolution to interpretation (A). That cross-reference is
added directly to `12`'s file (see the edit note below) — this file no longer carries its own
competing analysis of dedicated-sending-IP volume thresholds as the live interpretation of "why
multiple IPs," since James's answer clarifies that was not what he meant. The original SendGrid/
Mailgun/Postmark volume-threshold analysis this file previously contained is retired as
irrelevant to what James was actually asking about — it is not deleted from this doc set's
history via version control, but it is no longer this file's operative content.

**Edit made to `machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md`:** add a
one-line cross-reference in that file's "Multilogin profile/account management" section pointing
back at this resolution (see that file's own edit, made alongside this one) — do not duplicate
the profile-per-account design in both places; `12` remains the single source of truth for it.

## Interpretation (B), resolved: separate hosting per brand — confirmed wanted, and genuinely
underspecified

**James's words: "Separate hosting per brand will be important."** This confirms interpretation
(B) — per-brand hosting/network distinction — as a real, wanted requirement, not a
presentation-only routing nuance. This is a materially different answer than this file's original
deferral record assumed: the original record treated (B) as **already closed** by
`machine-1-tenancy-core/02`'s `Brand.custom_domain` column plus `04-cors-and-ratelimit-
retrofit.md`'s CORS-resolution wiring (hostname/DNS-based routing on one shared backend process,
per the Cloudflare-for-SaaS/AWS multi-tenant-routing precedent that record cited). James's "will
be important" signal does not read as satisfied by "different hostnames pointed at the same
backend process" — it reads as wanting some real degree of separation beyond shared-process
domain routing.

**This creates a genuine, undischarged tension this doc set has not resolved, and this section
does not invent an answer to it.** Per this task's explicit instruction, this file does **not**
spec a full infrastructure design (no Docker/container-topology plan, no per-brand deployment
pipeline, no decision on whether "separate hosting" means separate backend processes, separate
containers, separate VMs, or something else) — doing so here would be guessing at a requirement
James has only gestured at, not specified. What this section does instead:

- **Names the tension explicitly.** `machine-1-tenancy-core/02-schema-and-migration.md`'s `Brand`
  model and `04-cors-and-ratelimit-retrofit.md`'s CORS retrofit are both built on the premise of
  **one shared backend process serving every brand**, distinguished only by `custom_domain` at
  the CORS/routing layer — the entire tenancy-core design's ADR (`docs/adr/0018-tenancy-model.md`,
  via chunk `01`) explicitly rejects schema-per-tenant/database-per-tenant and, by extension,
  process-per-tenant, as unnecessary complexity for a product with no cross-brand data-isolation
  requirement. "Separate hosting per brand" said plainly by the platform's own leadership is in
  tension with that rejection, at least at face value — either James means something the existing
  design already satisfies (e.g. "brands must look/feel separately hosted to an outside visitor,"
  which domain-based routing already achieves), or he means literal separate deployed
  instances/containers per brand, which the current design does not provide at all and would be a
  real, non-trivial infrastructure change (new provisioning automation, new per-brand deployment
  pipeline, a question of shared vs. per-brand database access from each instance, etc.).
- **Does not guess which of those two readings is correct.** This is flagged as a concrete open
  question for the next round of questions to James — see
  `task-orchestration/README.md`'s new "Open questions blocking further work" section, item 8,
  which cross-references back to this file.
- **Leaves `02` and `04`'s existing design in place, unmodified, pending that answer.** Nothing in
  this section changes `Brand.custom_domain`, the CORS retrofit, or any other already-specified
  chunk's scope. If James's eventual clarification confirms literal separate hosting is wanted, a
  new chunk (not written here) will need to spec that infrastructure change explicitly — this
  section's job is only to flag that the current design does not yet satisfy the stated
  requirement, not to build the replacement.

## Recommendation

- **Interpretation (A)** — resolved, no action needed beyond the cross-reference already made in
  `12`'s file. Treat this interpretation as closed.
- **Interpretation (B)** — confirmed as a real, wanted requirement, but **not yet actionable** as
  a concrete infrastructure spec. Do not build anything under this interpretation until the open
  question above (`README.md`'s "Open questions blocking further work," item 8) gets a specific
  answer from James on what "separate hosting" concretely means. Until then, `machine-1-tenancy-
  core/02` and `04`'s existing shared-backend, domain-routed design remains this doc set's
  implemented behavior — it is flagged as potentially insufficient, not replaced.

## Files to create

- None. This chunk remains a decision record, now a resolution record rather than a deferral
  record — no code, no new infrastructure, no migration.

## Files to edit

- `machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md` — add the cross-reference
  described in interpretation (A) above.
- `task-orchestration/README.md` — dependency graph, merge order, and gap-tracking sections
  updated to reference this file under its new name/status; new "Open questions blocking further
  work" section added, cross-referencing this file's interpretation (B) as item 8.

## Do not touch

- Do not provision any dedicated/warmed sending IP, IP-warming schedule, or SMTP relay
  infrastructure anywhere in the codebase or deployment config as a result of this chunk —
  interpretation (A) is resolved as being about Multilogin account-profile diversity, not
  sending-IP reputation, so the original deferral record's "do not build a dedicated sending IP"
  guidance still holds, just for a different reason now (it was never what James meant, not
  merely "not yet justified by volume").
- Do not build a per-brand hosting/deployment infrastructure design as part of this chunk — see
  interpretation (B) above; that is explicitly deferred to a future chunk pending a specific
  answer from James, not something to improvise here.
- Do not modify `backend/app/modules/outreach/service.py`, `backend/app/services/email_service.py`,
  `backend/docker/docker-compose.yml`, or any CORS/domain-routing code as part of this chunk —
  all remain read-only citations here.

## Verification

Since this chunk builds nothing, its "verification" is a documentation checklist, not a test
suite:

- Confirm this file is linked from `task-orchestration/README.md`'s dependency graph (as `M1_06`,
  now under its resolved name) and from its gap-tracking/confirmed-decisions sections.
- Confirm `machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md` carries the new
  cross-reference back to this file's interpretation (A) resolution.
- Confirm `task-orchestration/README.md`'s "Open questions blocking further work" section lists
  interpretation (B)'s "what does separate hosting per brand actually mean" question, cross-
  referenced back to this file.
- Confirm no other chunk in this doc set silently assumes either that dedicated sending IPs exist/
  are planned (interpretation A, still not being built, just for a corrected reason) or that
  literal separate per-brand hosting already exists (interpretation B, confirmed wanted but not
  yet built) — re-check `machine-2-parallel-tracks/05-outreach-canspam-send-compliance.md` and
  `machine-2-parallel-tracks/06-linkedin-outreach-send.md` for the former, and
  `machine-1-tenancy-core/02-schema-and-migration.md`/`04-cors-and-ratelimit-retrofit.md` for the
  latter; as of this resolution pass, none of them do.
