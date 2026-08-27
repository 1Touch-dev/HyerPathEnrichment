# 0020. Billing provider: Stripe, candidate-level subscriptions, event-ledger idempotency

- **Status:** Accepted
- **Date:** 2026-08-27

## Context

This chunk introduces the first payment-provider integration anywhere in this repo — no
`stripe` (or any payment provider) package exists in `backend/requirements.txt`, no
`backend/app/integrations/stripe/` directory exists, and no billing-related table exists before
this chunk. Per `docs/adr/README.md`'s "When to add an ADR" criteria, this is a new
external-dependency/storage pattern (new tables, new external API, new webhook auth model), so an
ADR is mandatory, not optional.

Three decisions needed recording:

1. Which payment provider to integrate with, given real alternatives exist.
2. Whether a subscription belongs to a `Brand` (storefront) or to the `User` (candidate) — this
   repo already has a settled tenancy model (`docs/adr/0019-tenancy-model.md`) that constrains the
   answer.
3. How to handle the fact that a webhook provider may redeliver the same event more than once.

## Decision

We chose **Stripe** over **Paddle/Chargebee**, **subscription-per-candidate** over
**subscription-per-brand**, and an **event-ledger primary-key dedup table** over an
audit-log-only approach to webhook idempotency, for the following reasons:

1. **Stripe over Paddle/Chargebee.** Stripe Billing/Checkout is the de facto standard for
   subscription SaaS, has first-class webhook signature verification, and needs no self-hosted
   component. Per `docs.stripe.com/webhooks`, Stripe signs every webhook payload with a
   `Stripe-Signature` header that the receiving server verifies against a shared webhook secret —
   no self-hosted signing/verification infrastructure is required beyond that header check, which
   is exactly the shape `backend/app/integrations/stripe/client.py`'s
   `verify_webhook_signature` implements.

   We name the tradeoff honestly rather than omitting it: Paddle (and similar
   merchant-of-record providers) absorb sales-tax/VAT compliance liability as part of their
   ~5%+$0.50-per-transaction pricing, versus Stripe's ~2.9%+$0.30, where the merchant (this
   business) remains the merchant of record and is responsible for its own tax compliance. This
   repo chose control — direct ownership of the customer/subscription relationship, Stripe's
   broader ecosystem (Checkout, Billing Portal, test-mode tooling), and the lower per-transaction
   rate — over paying a premium to transfer that liability to the provider. If this business's tax
   footprint grows into jurisdictions where self-managed compliance becomes costly, that is a
   reason to revisit this ADR, not a reason to avoid recording the tradeoff now.

2. **Subscription-per-candidate, not per-brand.** `docs/adr/0019-tenancy-model.md` establishes
   that `Brand` is "a presentation/marketing concept for running multiple branded storefronts
   (custom domain, chatbot tone/branding, landing-page tier) on top of that one shared pool — not
   a per-agency data boundary," and that `Brand` has "no FK from any business table back to it
   except the two presentation-only columns" it names. A billing subscription is exactly the kind
   of business-table relationship that ADR already rules out attaching to `Brand`: billing follows
   the person who consumes the enriched content, not the storefront they happened to sign up
   through. Concretely, `UserSubscription.user_id` is a foreign key to `users.id`; no billing table
   in this chunk carries an FK to `brands.id`, matching 0019's Decision §1 that `Brand` is "not a
   tenancy mechanism" and its Consequences section, which lists no billing relationship for
   `Brand` at all. A candidate keeps their subscription even if they never touch that brand's site
   again — the storefront they signed up through has no bearing on what they're paying for.

3. **Webhook idempotency via a primary-key dedup ledger, not an audit-log afterthought.** Per
   `docs.stripe.com/webhooks#handle-duplicate-events`, Stripe states an explicit at-least-once
   delivery guarantee — the same event can be delivered more than once, and receivers are expected
   to deduplicate on `event.id`. `StripeWebhookEvent.stripe_event_id` is declared as the table's
   **primary key**, not a unique-indexed column on an otherwise audit-shaped table, specifically so
   that a second delivery of the same event is a straightforward existence check
   (`event_already_processed`) before any state-changing work runs, rather than a downstream
   consequence of an audit log that happens to also prevent duplicates. The ledger doubles as an
   audit trail, but its primary reason to exist is dedup, driven directly by Stripe's own
   documented delivery semantics.

## Tradeoffs

- Choosing Stripe over a merchant-of-record provider means this business, not the payment
  provider, is responsible for its own sales-tax/VAT compliance as it grows — a cost this ADR
  accepts in exchange for the lower per-transaction rate and direct control, per Decision §1.
- Subscription-per-candidate means there is no product surface for a brand-level or team/seat
  billing plan today. If a future requirement needs org-level billing (e.g. a real third-party
  agency paying for a block of candidates), that is a new ADR and a new schema change — this
  design does not degrade gracefully into one, the same way 0019 already flags for row-level
  tenancy.
- The `stripe_event_id` primary-key ledger grows unboundedly with webhook volume and is never
  pruned by this chunk; that is an accepted cost of correctness (never losing the dedup key) over
  storage minimization.

## Consequences

- `backend/app/modules/billing/models.py` (`UserSubscription.user_id` FK to `users.id`, never to
  `brands.id`; `StripeWebhookEvent.stripe_event_id` as primary key)
- `backend/app/integrations/stripe/client.py` (`verify_webhook_signature` — the signature-check
  entry point referenced in Decision §1)
- `backend/app/modules/billing/repository.py` (`event_already_processed` / `mark_event_processed`,
  the dedup operations referenced in Decision §3)
- Forward-reference: the (deferred) `webhook_router.py` and `service.py` are the eventual callers
  of the repository functions named above; this ADR's decisions constrain their design once they
  are implemented, per `task-orchestration/post-tenancy-features/01-billing-stripe-integration.md`.
