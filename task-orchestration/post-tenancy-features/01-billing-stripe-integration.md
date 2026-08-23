# Post-Tenancy Features, Chunk 1 — Billing (Stripe Integration)

## Depends on

`post-tenancy-retrofit/04-tenant-isolation-test-suite.md` green on real Postgres.
`machine-1-tenancy-core`'s `Organization` model (billing is per-org — an agency's subscription
covers its whole team, not one recruiter individually).

## Ground truth (verified 2026-08-22)

No Stripe (or any payment provider) integration exists anywhere in this repo today —
`backend/requirements.txt` has no `stripe` package, no `backend/app/integrations/stripe/` or
similar directory exists, and no billing-related model/table exists. This chunk is genuinely
net-new, not a retrofit.

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
  `python -m alembic heads`)
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
`docs/adr/README.md`'s index at implementation time, the same caveat as `machine-1`'s tenancy
ADR) covering: why Stripe over an alternative (Stripe Billing/Checkout is the de facto standard
for subscription SaaS, has first-class webhook signature verification, and needs no self-hosted
component — contrast with, say, a self-hosted alternative that would need a new
`docker-compose.yml` service); why subscription-per-org, not per-user (mirrors the tenancy ADR's
"org owns the relationship" framing); and the webhook-idempotency approach (see below).

## `backend/app/modules/billing/models.py`

```python
class OrganizationSubscription(Base):
    __tablename__ = "organization_subscriptions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    plan_tier: Mapped[str] = mapped_column(String(32), default="free", nullable=False)  # "free"|"starter"|"growth"|"enterprise"
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    # Mirrors Stripe's own subscription.status values ("active", "past_due", "canceled",
    # "incomplete", "trialing") rather than inventing a bespoke vocabulary — this table is a
    # read-side cache of Stripe's state, not a system of record competing with Stripe's own.
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seats_included: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class StripeWebhookEvent(Base):
    """Processed-event ledger for webhook idempotency — Stripe explicitly documents
    that the same event may be delivered more than once; this table is the dedup key,
    not an audit log (though it doubles as one)."""

    __tablename__ = "stripe_webhook_events"

    stripe_event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

## `backend/app/core/config.py`

```python
# Billing (docs/adr/00XX-billing-provider.md): Stripe integration. Default disabled — no
# billing enforcement until an operator explicitly opts in with real Stripe keys.
enable_billing: bool = Field(default=False, alias="ENABLE_BILLING")
stripe_secret_key: SecretStr = Field(default=SecretStr(""), alias="STRIPE_SECRET_KEY")
stripe_webhook_secret: SecretStr = Field(default=SecretStr(""), alias="STRIPE_WEBHOOK_SECRET")
stripe_price_id_starter: str = Field(default="", alias="STRIPE_PRICE_ID_STARTER")
stripe_price_id_growth: str = Field(default="", alias="STRIPE_PRICE_ID_GROWTH")
```

(`SecretStr` — check whether `multilogin_password`'s existing `SecretStr` usage in this same
file is the established convention for secret-shaped config values; if so, follow it exactly as
shown above; if this repo uses a different secret-handling convention elsewhere, match that
instead.)

Add `validate_billing_settings()` following the exact `validate_tier1_settings()`/
`validate_outreach_settings()` shape (fail fast, no-op when `enable_billing` is `False`, list
missing key names only).

## `backend/app/integrations/stripe/client.py`

Thin wrapper — do not scatter raw `stripe.*` SDK calls across `service.py`; centralize:

```python
class StripeClient:
    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        stripe.api_key = api_key or settings.stripe_secret_key.get_secret_value()

    async def create_customer(self, *, org_id: UUID, email: str) -> str: ...
    async def create_checkout_session(self, *, customer_id: str, price_id: str, success_url: str, cancel_url: str) -> str: ...
    async def create_billing_portal_session(self, *, customer_id: str, return_url: str) -> str: ...
    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> "stripe.Event": ...
```

The Stripe Python SDK's HTTP calls are synchronous — wrap each call in `asyncio.to_thread(...)`
inside these async methods (matching this repo's existing convention for wrapping sync SDK/
driver calls, e.g. `asyncio.to_thread(connect_selenium, port)` in
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
webhook signature. Do not add `CurrentUser`/`VerifiedUser` to this route. It also must **not**
be behind the org-scoped CORS retrofit from `machine-1/04` (Stripe's servers aren't a browser
origin) — verify it is exempted the same way `opt_out`/`dsar` webhook-style public routes are
already exempted from whatever CORS-relevant assumptions exist, if any (in practice, CORS only
applies to browser-originated requests, so a server-to-server webhook is unaffected regardless —
confirm this understanding is correct for this codebase's setup before assuming no action is
needed).

Handle at minimum: `checkout.session.completed` (create `OrganizationSubscription` row + link
`stripe_customer_id`), `customer.subscription.updated` (sync `status`/`current_period_end`/
`plan_tier`), `customer.subscription.deleted` (set `status="canceled"`).

## `backend/app/modules/billing/router.py`

```python
router = APIRouter(prefix="/api/billing", tags=["billing"], route_class=EnvelopeAPIRoute)

@router.post("/checkout-session")
async def create_checkout_session(
    body: CreateCheckoutSessionRequest,
    user: OrgScopedUser,   # machine-1's dependency — only org members can start a checkout
    db: AsyncSession = Depends(get_db_session),
) -> CheckoutSessionResponse: ...

@router.post("/portal-session")
async def create_portal_session(
    user: OrgScopedUser,
    db: AsyncSession = Depends(get_db_session),
) -> PortalSessionResponse: ...

@router.get("/subscription", response_model=OrganizationSubscriptionResponse)
async def get_subscription(
    user: OrgScopedUser,
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationSubscriptionResponse: ...
```

Restricting checkout/portal/subscription-status endpoints to `OrgScopedUser` (from
`machine-1-tenancy-core/03-auth-org-id-claim.md`) rather than plain `VerifiedUser` is
deliberate: a direct candidate with no org has nothing to bill (billing is per-agency).

## Seat enforcement — explicitly out of scope for this chunk

This chunk creates the subscription/billing plumbing and records `seats_included`, but **does
not** enforce a seat cap anywhere (e.g. blocking a new recruiter signup once an org exceeds
`seats_included`). Flag this as a deliberate scope cut in the PR description — seat enforcement
touches the signup/invite flow this doc set never fully specified (see
`machine-1-tenancy-core/03`'s "Org bootstrap on signup" section, which itself deferred invite-
flow design) and is a reasonable, separate follow-up chunk.

**Follow-up (closed):** this gap is now closed by `machine-1-tenancy-core/05-org-invite-flow.md`.
The enforcement check lives at that chunk's `POST /api/orgs/{org_id}/invites` endpoint (the
invite-creation path), not at signup itself — it rejects with 402 before a new invite is created
whenever `(active org members) + (pending, unexpired invites) + 1 > OrganizationSubscription.
seats_included`. A future reader landing on this section should treat seat enforcement as
implemented, not still outstanding — see that chunk's file for the full rule (including the
fail-open-only-on-absent-subscription exception and the resend/upsert edge case).

## Do not touch

- `backend/app/modules/orgs/` — read-only reference (`Organization.id`), not modified by this
  chunk beyond the new `OrganizationSubscription` FK relationship.
- Any of the post-tenancy-retrofit domain modules — billing has no interaction with job matching/
  outreach/documents/portfolio/admin data.
- `backend/docker/docker-compose.yml`'s existing services — no new container; only new `api`
  service env vars for the Stripe keys.

## Verification

- Webhook signature verification test: a request with an invalid/missing `stripe-signature`
  header is rejected (400), never processed.
- Idempotency test: the same `event.id` delivered twice only creates/updates state once (second
  delivery short-circuits via `event_already_processed`).
- `OrgScopedUser`-gating test: a direct candidate (`org_id=None`) gets 403 on all three
  `billing/router.py` endpoints.
- Use Stripe's test-mode API keys and the Stripe CLI's `stripe trigger` command (or an
  equivalent fixture payload) to simulate `checkout.session.completed` end-to-end in a test —
  do not only unit-test the handler function in isolation; at least one test should exercise the
  full webhook route with a real (test-mode) Stripe-shaped payload and signature.
