# Post-Tenancy Features, Chunk 1 — Billing (Stripe Integration)

## Depends on

`machine-1-tenancy-core`'s `Brand` model exists (`brands` table, presentation-only — not a
data-isolation boundary). Billing in this model is **candidate-level**, not brand-level: a `Brand`
is a storefront, not a paying tenant, so this chunk has no dependency on any brand-scoped
subscription seat count and does not gate on the retrofit wave (that wave no longer exists — see
`README.md`'s merge order).

## Ground truth (verified 2026-08-22)

No Stripe (or any payment provider) integration exists anywhere in this repo today —
`backend/requirements.txt` has no `stripe` package, no `backend/app/integrations/stripe/` or
similar directory exists, and no billing-related model/table exists. This chunk is genuinely
net-new, not a retrofit.

## Model shift: `OrganizationSubscription` → `UserSubscription`

Billing in this product is a **freemium, candidate-facing paywall**, not an agency/org seat
license. There is no `Organization`/`Brand`-level subscription anywhere in this doc set — each
individual candidate (`User` row) has at most one `UserSubscription`. A `Brand` is a marketing
storefront a candidate signed up through (`candidates.signup_brand_id`); it has no billing
relationship of its own and never appears as an FK target on any billing table.

## Files to create

- `backend/app/integrations/stripe/__init__.py`
- `backend/app/integrations/stripe/client.py`
- `backend/app/modules/billing/__init__.py`
- `backend/app/modules/billing/models.py`
- `backend/app/modules/billing/schemas.py`
- `backend/app/modules/billing/repository.py`
- `backend/app/modules/billing/service.py`
- `backend/app/modules/billing/router.py`
- `backend/app/modules/billing/webhook_router.py`
- `backend/alembic/versions/0XX_billing_stripe_tables.py` (real number TBD — re-run
  `python -m alembic heads` at implementation time)
- `docs/adr/00XX-billing-provider.md` (see ADR requirement below)

## Files to edit

- `backend/requirements.txt` — add `stripe` (pin to whatever the latest stable major version is
  at implementation time; check PyPI, do not guess a version number here).
- `backend/app/core/config.py`
- `backend/app/main.py` — register `billing.router` and `billing.webhook_router`.
- `backend/docker/docker-compose.yml` — no new service needed (Stripe is an external API, not a
  self-hosted container); only new env vars on the `api` service.

## ADR requirement

Per `docs/adr/README.md`'s "When to add an ADR" criteria, introducing a payment provider
integration is a new external-dependency/storage pattern (new tables, new external API, new
webhook auth model) — write `docs/adr/00XX-billing-provider.md` (next free number; re-verify via
`docs/adr/README.md`'s index at implementation time) covering: why Stripe over an alternative
(Stripe Billing/Checkout is the de facto standard for subscription SaaS, has first-class webhook
signature verification, and needs no self-hosted component); why subscription-per-candidate, not
per-brand (billing follows the person who consumes the enriched content, not the storefront they
signed up through — a candidate keeps their subscription even if they never touch that brand's
site again); and the webhook-idempotency approach (see below, unchanged from the original design).

## `backend/app/modules/billing/models.py`

```python
class UserSubscription(Base):
    """Candidate-level freemium subscription. One row per paying-or-formerly-paying
    User; free/never-subscribed candidates simply have no row here (absence of a
    row means "free tier," not an error state — see service.py's get_effective_tier)."""

    __tablename__ = "user_subscriptions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    plan_tier: Mapped[str] = mapped_column(String(32), default="free", nullable=False)  # "free"|"premium"
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    # Mirrors Stripe's own subscription.status values ("active", "past_due", "canceled",
    # "incomplete", "trialing") rather than inventing a bespoke vocabulary — this table is a
    # read-side cache of Stripe's state, not a system of record competing with Stripe's own.
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class StripeWebhookEvent(Base):
    """Processed-event ledger for webhook idempotency — Stripe explicitly documents
    that the same event may be delivered more than once; this table is the dedup key,
    not an audit log (though it doubles as one). Unchanged in shape from the prior
    org-billing design — idempotency is a property of the webhook transport, not of
    what the event's payload happens to be about."""

    __tablename__ = "stripe_webhook_events"

    stripe_event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

There is no `seats_included` column — a candidate subscription is a single seat by construction
(you cannot buy premium access "for a team" in this model). Do not carry that column forward from
the old design; it has no meaning here.

## `backend/app/core/config.py`

```python
# Billing (docs/adr/00XX-billing-provider.md): Stripe integration. Default disabled — no
# billing enforcement until an operator explicitly opts in with real Stripe keys.
enable_billing: bool = Field(default=False, alias="ENABLE_BILLING")
stripe_secret_key: SecretStr = Field(default=SecretStr(""), alias="STRIPE_SECRET_KEY")
stripe_webhook_secret: SecretStr = Field(default=SecretStr(""), alias="STRIPE_WEBHOOK_SECRET")
stripe_price_id_premium: str = Field(default="", alias="STRIPE_PRICE_ID_PREMIUM")
```

(`SecretStr` — check whether `multilogin_password`'s existing `SecretStr` usage in this same file
is the established convention for secret-shaped config values; if so, follow it exactly as shown
above; if this repo uses a different secret-handling convention elsewhere, match that instead.)

Add `validate_billing_settings()` following the exact `validate_tier1_settings()`/
`validate_outreach_settings()` shape (fail fast, no-op when `enable_billing` is `False`, list
missing key names only).

Only one paid price id (`stripe_price_id_premium`) — there is no tiered
starter/growth/enterprise ladder in a candidate-facing freemium product; keep the config surface
as small as the actual pricing model, not as large as the old org-seat design's.

## `backend/app/integrations/stripe/client.py`

Thin wrapper — do not scatter raw `stripe.*` SDK calls across `service.py`; centralize:

```python
class StripeClient:
    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        stripe.api_key = api_key or settings.stripe_secret_key.get_secret_value()

    async def create_customer(self, *, user_id: UUID, email: str) -> str: ...
    async def create_checkout_session(self, *, customer_id: str, price_id: str, success_url: str, cancel_url: str) -> str: ...
    async def create_billing_portal_session(self, *, customer_id: str, return_url: str) -> str: ...
    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> "stripe.Event": ...
```

The Stripe Python SDK's HTTP calls are synchronous — wrap each call in `asyncio.to_thread(...)`
inside these async methods (matching this repo's existing convention for wrapping sync SDK/driver
calls, e.g. `asyncio.to_thread(connect_selenium, port)` in
`backend/app/integrations/linkedin/client.py` line 95) rather than blocking the event loop
directly.

## `backend/app/modules/billing/webhook_router.py`

```python
router = APIRouter(prefix="/api/billing/webhooks", tags=["billing"])

@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    event = StripeClient().verify_webhook_signature(payload, signature)  # raises 400 on bad signature — let it propagate

    if await repository.event_already_processed(db, event.id):
        return {"status": "already_processed"}  # idempotency — Stripe redelivers events

    await service.handle_webhook_event(db, event)
    await repository.mark_event_processed(db, event.id, event.type)
    return {"status": "processed"}
```

This endpoint must **not** go through the standard cookie-auth (`CurrentUser`/`VerifiedUser`)
dependency — Stripe calls it directly, unauthenticated by cookie, authenticated instead by the
webhook signature. Do not add `CurrentUser`/`VerifiedUser` to this route. This part of the design
is unchanged from the original org-billing spec: webhook idempotency and signature verification
are correct regardless of whether the subscription underneath is org- or candidate-scoped, so it
carries forward as-is.

Handle at minimum: `checkout.session.completed` (create `UserSubscription` row + link
`stripe_customer_id` to the checking-out `User`, resolved via `client_reference_id` set at
checkout-session creation — see router below), `customer.subscription.updated` (sync `status`/
`current_period_end`/`plan_tier`), `customer.subscription.deleted` (set `status="canceled"`,
which flips the candidate back to the free/blurred-preview experience — see paywall section).

## `backend/app/modules/billing/router.py`

```python
router = APIRouter(prefix="/api/billing", tags=["billing"], route_class=EnvelopeAPIRoute)

@router.post("/checkout-session")
async def create_checkout_session(
    body: CreateCheckoutSessionRequest,
    user: VerifiedUser,   # any verified candidate can start a checkout — no brand/org gate
    db: AsyncSession = Depends(get_db_session),
) -> CheckoutSessionResponse: ...

@router.post("/portal-session")
async def create_portal_session(
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> PortalSessionResponse: ...

@router.get("/subscription", response_model=UserSubscriptionResponse)
async def get_subscription(
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> UserSubscriptionResponse: ...
```

Gating on plain `VerifiedUser` (not an org-scoped dependency — no such dependency exists in this
model, since `Brand` never gates data access) is deliberate: **every** candidate is a potential
payer, whether or not they signed up through a branded storefront. This is the single biggest
shape change from the prior design, which restricted these endpoints to `OrgScopedUser` on the
theory that only agency-affiliated recruiters could bill; that theory does not survive the pivot
to a single shared candidate pool with per-candidate freemium billing.

## Freemium paywall: blurred/teaser preview for non-paying candidates

This is the actual product mechanism this chunk exists to support, not just a billing plumbing
exercise. Enriched content endpoints (job matches, outreach drafts, CV feedback reports — the
exact list is this chunk's implementer's call after reading current response shapes, but at
minimum `job_matching`'s match list/detail and `documents`'s CV feedback report) must, for a
candidate without an `active`/`trialing` `UserSubscription`, return a **teaser** shape rather than
either the full content or a bare 403:

```python
async def get_effective_tier(db: AsyncSession, user_id: UUID) -> Literal["free", "premium"]:
    subscription = await repository.get_subscription_for_user(db, user_id)
    if subscription is None:
        return "free"
    return "premium" if subscription.status in ("active", "trialing") else "free"
```

```python
class JobMatchResponse(BaseModel):
    ...
    is_blurred: bool
    # When is_blurred=True, `match_reasons`/`ai_summary`-shaped fields carry a short,
    # non-actionable teaser string ("Unlock to see why this role matches you") instead
    # of the real enriched text — never send the real content and a blur flag together;
    # a client-side-only blur is trivially bypassed by reading the API response body.
```

**Decision (definitive, not implementer's choice): the blur/teaser substitution happens
server-side, in the response payload itself, not as a CSS/UI-only blur over real data.** A UI-only
blur that ships the real enriched text in the JSON response is a real, immediately-exploitable
security-via-obscurity mistake (open devtools, read the network tab) — this doc set does not
repeat that mistake. The frontend only needs to render `is_blurred` as a visual treatment; it must
never need to hide already-received real data.

## Freemium conversion-rate assumptions

Ground any capacity/pricing/revenue-projection language elsewhere in this doc set (or in the
eventual ADR's "why this pricing" section) against the **1-5% freemium conversion benchmark
range** — this is the widely-cited range for consumer freemium products converting free users to
paid, and this product (candidate-facing, freemium, blurred-preview) fits that category far more
than a B2B seat-license SaaS product would (which typically converts at a much higher rate off a
smaller, more qualified top-of-funnel). Concretely: do not size Stripe test fixtures, load
assumptions, or the ADR's "expected revenue" discussion around a rate outside 1-5% without an
explicit, cited reason for deviating (e.g. a specific paywall placement shown by early data to
convert unusually well) — and if no such data exists yet, default to the **low** end (1-2%) for
any planning number, since freemium products conservatively skew toward the low end absent a
strong activation hook, and this chunk's paywall (a teaser/blur, not a hard feature gate) is a
softer conversion trigger than, say, a usage-limit gate would be.

## Do not touch

- `backend/app/modules/brands/` (or wherever `machine-1-tenancy-core/02` lands the `Brand` model)
  — read-only reference (`Brand.id`, used only if a future chunk wants brand-level billing
  analytics; this chunk creates no FK from any billing table to `brands.id`).
- Any of the deleted `post-tenancy-retrofit` modules — that wave no longer exists; billing has no
  interaction with job matching/outreach/documents/portfolio/admin access-control logic in this
  model, since none of those are tenant-isolated in the first place.
- `backend/docker/docker-compose.yml`'s existing services — no new container; only new `api`
  service env vars for the Stripe keys.

## Verification

- Webhook signature verification test: a request with an invalid/missing `stripe-signature`
  header is rejected (400), never processed.
- Idempotency test: the same `event.id` delivered twice only creates/updates state once (second
  delivery short-circuits via `event_already_processed`).
- Paywall test: a candidate with no `UserSubscription` row gets `is_blurred=True` teaser payloads
  from enriched-content endpoints, never the real underlying text in the response body (assert on
  the raw JSON, not just the `is_blurred` flag — the whole point is that the real content must be
  absent, not merely flagged).
- Paywall test: a candidate with an `active` `UserSubscription` gets full, unblurred content from
  the same endpoints.
- Downgrade test: `customer.subscription.deleted` flips a previously-premium candidate's
  `get_effective_tier` back to `"free"` on their very next request (no lingering premium access
  past cancellation).
- Use Stripe's test-mode API keys and the Stripe CLI's `stripe trigger` command (or an equivalent
  fixture payload) to simulate `checkout.session.completed` end-to-end in a test — do not only
  unit-test the handler function in isolation; at least one test should exercise the full webhook
  route with a real (test-mode) Stripe-shaped payload and signature.
