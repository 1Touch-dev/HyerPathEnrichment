# Machine 1, Chunk 6 — Outbound IP Strategy: Explicit Decision to Defer

## Status: decision record, no code, no new infrastructure

This chunk builds **nothing**. It exists so the original ask's "multiple different ips displaying
account info or updates" phrase does not remain a silently unaddressed gap in this doc set — it is
an explicit, documented decision to defer, following the same "no-op stub with a real reason"
convention `03-auth-org-id-claim.md` already established for a different superseded scope. Unlike
`03`, this chunk was never implemented scope to begin with; it is a disambiguation-and-deferral
record for an ambiguous requirement, not a supersession of previously-planned code.

## Depends on

- `machine-2-parallel-tracks/05-outreach-canspam-send-compliance.md` — for the real-sending-
  infrastructure gap this chunk's interpretation (A) below relies on (that chunk's own "Ground
  truth" section is the source for "no SMTP-sending pipeline exists for outreach today").
- `04-cors-and-ratelimit-retrofit.md` — for the domain-routing precedent this chunk's
  interpretation (B) below relies on (`Brand.custom_domain` + CORS allow-list resolution).

## The ambiguity

The original task brief that generated this doc set included the phrase "multiple different ips
displaying account info or updates," without further detail. Read literally, this admits (at
least) two materially different interpretations:

- **(A) Email/LinkedIn-sending reputation protection** — the idea that outbound messages sent on
  behalf of different brands/accounts should originate from different IP addresses, for sender-
  reputation/deliverability reasons (dedicated IPs, IP warming).
- **(B) Per-brand hosting/network isolation** — the idea that each brand storefront should be
  served from a distinct IP address, for presentation/routing or perceived-isolation reasons.

Neither interpretation has a concrete design anywhere else in this doc set. This chunk resolves
the ambiguity by examining both against this repo's actual current state and closes it as an
explicit, reasoned deferral rather than leaving it to be silently assumed one way or the other by
a later reader.

## Interpretation (A): dedicated sending IPs for email/LinkedIn reputation

**Ground truth: no real sending pipeline exists yet to protect the reputation of.**
`OutreachService.send_message()` (`backend/app/modules/outreach/service.py`, lines 123-162,
verified 2026-08-24 — this chunk's line citation matches
`machine-2-parallel-tracks/05-outreach-canspam-send-compliance.md`'s own "Ground truth" section
exactly) does not transmit email over SMTP today; its own docstring states this explicitly ("no
email-sending infra targeting arbitrary third-party recipients exists in this repo today").
Marking a message `status="sent"` records the candidate's own action of copying/sending the text
themselves — there is no outbound send volume at all for a dedicated IP to protect.

The one real sending pipeline that does exist,
`backend/app/services/email_service.py`'s `EmailService` (SendGrid-backed, confirmed 2026-08-24 —
`from sendgrid import SendGridAPIClient`), sends only to the platform's own registered users
(job-completion notices, OTP/verification emails, digest emails — see its `EmailTemplate` enum),
never to an arbitrary third-party hiring-manager address a candidate supplies. Its volume is
nowhere near any vendor's documented dedicated-IP threshold:

- SendGrid recommends dedicated IPs only above roughly **50,000 emails/month**
  (https://www.twilio.com/en-us/resource-center/email-guide-ip-warm-up).
- Mailgun's stated threshold is roughly **100,000/month**, below which a shared IP is explicitly
  the better choice
  (https://help.mailgun.com/hc/en-us/articles/202453900-When-do-I-need-a-dedicated-IP-address).
- Postmark requires **300,000+/month** and states outright that dedicated IPs are "a bad idea for
  senders with lower volumes" (https://postmarkapp.com/dedicated-ips).

All three vendors are explicit that a low-volume dedicated IP **performs worse** than a shared
pool — a cold, low-traffic dedicated IP has no positive reputation history and looks more
suspicious to receiving mail servers than an established shared pool's reputation does. This is
the concrete reason to defer, not an arbitrary cutoff picked for convenience: provisioning a
dedicated IP today, at this repo's actual (zero) real-send volume, would make deliverability
*worse*, not better or even neutral.

## Interpretation (B): per-brand hosting/network isolation

**This repo's own design already handles this, with zero new infrastructure.** Multi-tenant/
multi-brand platforms route by hostname/DNS against shared infrastructure, not by provisioning a
distinct IP per tenant — this is the documented pattern from both:

- Cloudflare's own "Cloudflare for SaaS" docs
  (https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/), and
- AWS's own Networking & Content Delivery blog on SaaS tenant routing
  (https://aws.amazon.com/blogs/networking-and-content-delivery/tenant-routing-strategies-for-saas-applications-on-aws/).

Neither describes per-tenant IP provisioning anywhere in their respective multi-tenant routing
guidance; both describe shared infrastructure with hostname-based routing at the edge. This
repo's own `Brand.custom_domain` design (`machine-1-tenancy-core/02-schema-and-migration.md`,
`Brand` model, `custom_domain: Mapped[str | None]`, lines 59-64: "Custom domain for this brand's
storefront ... Used only for CORS origin resolution ... and storefront routing — never a query
filter") plus `04-cors-and-ratelimit-retrofit.md`'s "CORS retrofit — dynamic per-brand domain"
section (which resolves every active brand's `custom_domain` into a single shared
`CORSMiddleware` allow-list at startup, per that chunk's `_resolve_cors_origins` helper) already
**is** this exact hostname/DNS-routing pattern — one shared backend, N brand hostnames routed to
it, zero per-brand IP anywhere in the design. Interpretation (B) requires no new chunk, no new
infrastructure, and no further action beyond what `machine-1-tenancy-core/02` and `04` already
specify.

## Recommendation

**Defer building anything IP-specific under either interpretation.** Concretely:

- **Interpretation (A)** — do not provision any dedicated/warmed sending IP now. The concrete
  trigger condition for revisiting this is **sustained real outbound-send volume approaching the
  ~50,000-100,000 messages/month range** cited above, *and* only once real outreach-sending
  infrastructure actually exists to generate that volume in the first place (see
  `05-outreach-canspam-send-compliance.md`'s own explicit statement that CAN-SPAM compliance work
  "hardens the compliance shape of the existing 'draft + candidate sends it themselves' flow, it
  does not build an SMTP sender" — that sender does not exist yet either). This is therefore a
  **two-stage gate**, not a single threshold: (1) real outbound-send infrastructure must first be
  built (not part of this chunk, not part of `05`, tracked nowhere in this doc set today as active
  scope), and only then (2) does the volume threshold above become the relevant trigger to revisit
  dedicated IPs. Neither stage is close to being met today.
- **Interpretation (B)** — no separate action needed. `machine-1-tenancy-core/02`'s
  `Brand.custom_domain` column plus `04`'s CORS-resolution wiring already deliver
  hostname/domain-based per-brand routing on shared infrastructure, matching the Cloudflare/AWS
  precedent above exactly. Treat this interpretation as **already closed** by existing planned
  work, not as a gap needing a new chunk.

## Files to create

- None. This chunk is a decision record only.

## Files to edit

- None beyond `task-orchestration/README.md`'s dependency graph/gap-tracking section (see that
  file's "Gaps closed" table and dependency graph, updated alongside this chunk's creation).

## Do not touch

- Do not provision any dedicated/warmed sending IP, IP-warming schedule, or SMTP relay
  infrastructure anywhere in the codebase or deployment config as a result of this chunk.
- Do not add a per-brand IP, per-brand load balancer, or per-brand hosting target to
  `backend/docker/docker-compose.yml` or any deployment config — this would contradict
  interpretation (B)'s resolution above and duplicate infrastructure `machine-1-tenancy-core/02`
  and `04` already provide via hostname routing.
- Do not modify `backend/app/modules/outreach/service.py`, `backend/app/services/email_service.py`,
  or any CORS/domain-routing code as part of this chunk — both are read-only citations here,
  already owned and already correctly scoped by other chunks (`05` and `04` respectively).
- Do not silently assume, in any later chunk in this doc set, that per-brand or dedicated-per-
  sender IPs exist or are planned — if a later chunk's design depends on either, that is a
  contradiction of this decision record and should be flagged, not built around.

## Verification

Since this chunk builds nothing, its "verification" is a documentation checklist, not a test
suite:

- Confirm this file is linked from `task-orchestration/README.md`'s dependency graph (as `M1_06`)
  and from its gap-tracking/"Gaps closed" section (see that file's updates alongside this chunk).
- Confirm no other chunk in this doc set contradicts this decision by silently assuming per-brand
  or dedicated-sending IPs already exist or are being built — in particular, re-check
  `machine-2-parallel-tracks/05-outreach-canspam-send-compliance.md` and
  `machine-2-parallel-tracks/06-linkedin-outreach-send.md` (the two chunks closest to real
  outbound sending) for any such assumption; as of 2026-08-24 (this chunk's own verification
  pass), neither does.
- Confirm `machine-1-tenancy-core/02-schema-and-migration.md` and
  `04-cors-and-ratelimit-retrofit.md` remain the sole source of truth for per-brand
  routing/domain behavior — this chunk adds no competing or duplicate design.
