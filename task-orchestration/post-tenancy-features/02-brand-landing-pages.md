# Post-Tenancy Features, Chunk 2 — Brand Landing Pages

## Depends on

`machine-1-tenancy-core`'s `Brand` model (`slug`, `custom_domain`, `chatbot_config`, landing-page
tier config columns — see `machine-1-tenancy-core/02-schema-and-migration.md`).

## Goal

`Brand` is the primary org-level concept in this product — not a late add-on bolted onto an
existing agency-tenancy model. Every signup storefront, every candidate-facing landing experience,
and every piece of white-label presentation (custom domain, chatbot tone/config) hangs off
`Brand`. This chunk gives each `Brand` a public landing page — e.g. `acme-staffing.hyrepath.com`
— showcasing the brand (not an individual candidate), **plus** tier/segment sub-pages beneath it
so a brand can run more than one landing experience (e.g. a general page and a premium-tier
upsell page) without needing a second `Brand` row per variant. This is the **brand-level**
counterpart to the existing **candidate-level** public portfolio page
(`frontend/app/p/[slug]/page.tsx`, backed by `GET /api/portfolio/public/{slug}`), and reuses the
exact same subdomain-rewrite mechanism, extended to also recognize brand slugs.

Reminder for anyone touching this file who also worked with the pre-pivot version: `Brand` is
**presentation-only**. It is not a data-isolation boundary — there is one shared candidate/
recruiter pool, and nothing in this chunk (or anywhere else in this doc set) filters query results
by brand. A brand landing page's only job is to look and feel like a distinct storefront; it does
not gate who can be matched, contacted, or enriched.

## Ground truth (verified 2026-08-22)

The existing subdomain rewrite is deliberately generic in its pure-logic core but is wired today
only for candidate portfolios:

```26:45:frontend/src/lib/subdomain.ts
export function resolveSubdomainRewrite(
  host: string,
  enabled: boolean,
  rootDomain: string,
): string | null {
  ...
  const slug = match[1];
  return `/p/${slug}`;
}
```

```1:27:frontend/middleware.ts
export default function middleware(request: NextRequest) {
  const host = request.headers.get("host") ?? "";
  const enabled = process.env.PORTFOLIO_SUBDOMAINS_ENABLED === "true";
  const rootDomain = process.env.PORTFOLIO_SUBDOMAIN_ROOT ?? "";
  const rewritePath = resolveSubdomainRewrite(host, enabled, rootDomain);
  if (rewritePath) {
    return NextResponse.rewrite(new URL(rewritePath, request.url));
  }
  return NextResponse.next();
}
```

`resolveSubdomainRewrite` always returns `/p/${slug}` — it has no notion of "candidate slug vs.
brand slug," and the target route `/p/[slug]` always resolves against
`GET /api/portfolio/public/{slug}` (candidates only). This chunk must decide how a brand slug and
a candidate slug are disambiguated, since both now live under the same subdomain scheme and
`Brand.slug` (`machine-1-tenancy-core/02`) and `PortfolioProfile.slug`
(`backend/app/modules/portfolio/models.py` line 23) are **separate, independently-unique
columns today** — a collision (a brand and a candidate both choosing slug `"acme"`) is possible
and must be handled, not assumed away.

## Ambiguity resolved: separate route prefix, not slug-uniqueness enforcement

**Do not** attempt to enforce global slug uniqueness across `Brand.slug` and `PortfolioProfile.slug`
(that would require a cross-module unique constraint or an application-level check on every
candidate portfolio-slug write, coupling two modules that are otherwise intentionally decoupled).
Instead, give brand pages their **own** route prefix, `/b/{slug}` (brand), parallel to but
distinct from `/p/{slug}` (portfolio) — this makes the two slug namespaces genuinely independent
(a collision between a brand slug and a candidate slug is harmless; they resolve to different
pages) and requires no change to `portfolio_profiles.slug`'s existing uniqueness constraint.

## New in this chunk: tier/segment sub-pages (`/b/{slug}/{tier}`)

A single `Brand` can present more than one landing experience under its own slug — e.g.
`acme-staffing.hyrepath.com/b/acme/premium` as a distinct upsell page from the bare
`acme-staffing.hyrepath.com/b/acme` general page — **without** creating a second `Brand` row.
`{tier}` is a free-form, brand-authored path segment (not the same enum as billing's `plan_tier`
on `UserSubscription` — a brand's landing-page "tier" is a marketing/segment label the brand
picks for its own storefront copy, e.g. `"premium"`, `"grad"`, `"executive"`; it has no coupling
to whether the *visiting* candidate has a paid subscription). Storage-wise, this does not need a
new table: `Brand`'s existing `landing_page tier config` field (per
`machine-1-tenancy-core/02-schema-and-migration.md`'s column list) is a JSON/JSONB column keyed by
tier slug, e.g.:

```json
{
  "premium": { "headline": "Executive placements, faster.", "cta_label": "Apply as a senior candidate" },
  "grad": { "headline": "Your first role, made simple.", "cta_label": "Start your grad journey" }
}
```

A tier segment with no matching key in that config is a 404, not a fallback to the general page —
a brand author should get an obvious signal (broken link) if they reference a tier slug they
never configured, rather than silently serving generic copy under a URL that implies something
more specific.

## Files to create

- `frontend/app/b/[slug]/page.tsx`
- `frontend/app/b/[slug]/[tier]/page.tsx`
- `frontend/features/brand-pages/components/BrandLandingPage.tsx`
- `frontend/features/brand-pages/index.ts`
- `backend/app/modules/orgs/public_schemas.py` (or add to the existing
  `backend/app/modules/orgs/schemas.py` from `machine-1-tenancy-core/02` if that file is small
  enough that a second file would be unnecessary fragmentation — implementer's judgment, but
  keep public/authenticated-facing schemas clearly separated either via file or a clear naming
  convention, matching how `portfolio/schemas.py` separates `PortfolioProfileResponse` from
  `PublicPortfolioResponse`)
- `backend/app/modules/orgs/public_router.py`

(Module directory kept as `backend/app/modules/orgs/` per `machine-1-tenancy-core/02`'s existing
file layout for the `Brand` model — this chunk does not rename that directory; only the model
class inside it is `Brand`, not `Organization`.)

## `resolveSubdomainRewrite` retrofit (`frontend/src/lib/subdomain.ts`)

The function needs to disambiguate which namespace a subdomain belongs to. Since the pure-logic
function has no DB access (by design — "no I/O" is implied by its existing unit-testability
without a real `NextRequest`/Edge runtime, per its module docstring), **the disambiguation cannot
happen inside `resolveSubdomainRewrite` itself.** Two options:

- **(a)** Change the function's return type from `string | null` to a tagged union,
  `{ kind: "portfolio" | "brand"; slug: string } | null`, and have the **caller**
  (`middleware.ts`) decide the rewrite path — but the caller still has no DB access at the Edge
  runtime layer to know whether `slug` belongs to a brand or a candidate.
- **(b)** Keep `resolveSubdomainRewrite` exactly as-is (returning `/p/${slug}` always, unmodified
  — **do not change this function's existing signature or behavior**, since
  `frontend/features/portfolio/components/PublicPortfolioPage.test.tsx`-adjacent tests and any
  existing consumer depend on its current contract), and instead make **`/p/[slug]/page.tsx`
  itself** the disambiguation point: it already calls `GET /api/portfolio/public/{slug}` and
  calls `notFound()` on a non-OK response (see `frontend/app/p/[slug]/page.tsx` lines 10-11) —
  extend it to, on a 404 from the portfolio endpoint, fall through to a **second** check against
  the new brand public endpoint (`GET /api/brands/public/{slug}`), rendering `BrandLandingPage`
  instead if that succeeds, and only calling `notFound()` if *both* miss.

**Use approach (b).** It requires zero changes to the well-tested `resolveSubdomainRewrite`
pure function or `middleware.ts`, and keeps the "which page type is this" decision where it
already naturally belongs (a page component with real backend access), not in Edge middleware
that structurally can't make that call cheaply. The tradeoff — an extra backend round-trip for
every candidate portfolio slug that happens to also 404 — is a non-issue for actual portfolio
hits (which resolve on the first call) and vanishingly rare for the double-miss case (a slug
that's neither), so this is an acceptable read-path cost for the desired app-code-only
disambiguation. Document this reasoning inline in `frontend/app/p/[slug]/page.tsx`'s edit.

Do **not** implement option (a)'s tagged-union redesign — it would require either giving Edge
middleware a database dependency (a bigger architectural change than this chunk's scope, and
arguably its own ADR-worthy decision) or duplicating slug-existence logic into the Edge runtime,
neither of which is justified by this feature's actual requirements.

The new `/b/[slug]/[tier]/page.tsx` route does **not** need this same disambiguation dance — it
lives under the explicit `/b/` prefix already (see "Ambiguity resolved" above), so there is no
candidate-portfolio collision to fall through from; a miss there is simply a 404.

## `frontend/app/p/[slug]/page.tsx` edit

```typescript
export default async function PublicSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  const portfolioResponse = await backendFetchPublic(`/api/portfolio/public/${slug}`);
  if (portfolioResponse.ok) {
    const raw = await portfolioResponse.json();
    const profile = adaptPublicPortfolioProfile(unwrapEnvelopeData(raw));
    return <PublicPortfolioPage profile={profile} />;
  }

  // Falls through to the brand namespace on a portfolio miss — see
  // post-tenancy-features/02-brand-landing-pages.md for why this dual-check lives
  // here rather than in middleware.ts/subdomain.ts (no DB access at the Edge layer).
  const brandResponse = await backendFetchPublic(`/api/brands/public/${slug}`);
  if (!brandResponse.ok) notFound();

  const brandRaw = await brandResponse.json();
  const brand = adaptPublicBrand(unwrapEnvelopeData(brandRaw));
  return <BrandLandingPage brand={brand} />;
}
```

(`adaptPublicBrand` — new adapter function in `frontend/src/lib/api-adapter.ts`, following the
exact existing pattern of `adaptPublicPortfolioProfile` in that same file; read that function's
current implementation before writing the new one so field-mapping conventions match.)

Update `generateMetadata` in the same file with the identical fallback shape.

## `frontend/app/b/[slug]/[tier]/page.tsx` (new tier sub-page route)

```typescript
export default async function BrandTierPage({
  params,
}: {
  params: Promise<{ slug: string; tier: string }>;
}) {
  const { slug, tier } = await params;

  const brandResponse = await backendFetchPublic(`/api/brands/public/${slug}`);
  if (!brandResponse.ok) notFound();

  const brandRaw = await brandResponse.json();
  const brand = adaptPublicBrand(unwrapEnvelopeData(brandRaw));

  const tierConfig = brand.landingPageTierConfig?.[tier];
  if (!tierConfig) notFound(); // unconfigured tier slug — no silent fallback to general copy

  return <BrandLandingPage brand={brand} tierConfig={tierConfig} />;
}
```

`BrandLandingPage` takes an optional `tierConfig` prop; when present, it overrides the headline/
CTA copy it would otherwise render from the brand's general (non-tiered) fields, but keeps the
same layout/branding (logo, colors, custom domain framing) — a tier page is a copy variant of the
brand page, not a structurally different page type.

## `backend/app/modules/orgs/public_router.py`

```python
public_router = APIRouter(prefix="/api/orgs", tags=["orgs-public"], route_class=EnvelopeAPIRoute)

@public_router.get("/public/{slug}", response_model=PublicBrandResponse)
async def get_public_brand(
    slug: str, db: AsyncSession = Depends(get_db_session)
) -> PublicBrandResponse:
    """Unauthenticated — mirrors portfolio/router.py's get_public_profile exactly:
    no CurrentUser dependency, 404 on missing/inactive brand. This is the endpoint
    both the public /p/{slug} page's brand-page fallback and the /b/{slug}/{tier}
    tier sub-page (frontend/app/b/[slug]/[tier]/page.tsx) call — the tier config is
    part of this same response payload, not a separate endpoint."""
    brand = await repository.get_brand_by_slug(db, slug)
    if brand is None or not brand.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return PublicBrandResponse(
        name=brand.name,
        slug=brand.slug,
        landing_page_tier_config=brand.landing_page_tier_config,
        ...,
    )
```

`PublicBrandResponse` must **not** leak `custom_domain`, `chatbot_config`, internal ids beyond
what's needed for display, or any recruiter/candidate PII — it is a public, unauthenticated
response, same privacy bar as `PublicPortfolioResponse` already sets for candidate data. The tier
config it does expose (`landing_page_tier_config`) is brand-authored marketing copy, not internal
configuration, so it is safe to serve in full — do not filter individual tier entries.

Register `public_router` in `backend/app/main.py` next to the existing portfolio public router
registration.

## `frontend/features/brand-pages/components/BrandLandingPage.tsx`

A simple, brand-appropriate page — company name, headline/description copy, and (if this
effort's later scope wants it — flag as a follow-up, not required for this chunk's minimum) a
call-to-action linking to a candidate application or contact form. Keep the initial version as
minimal and close to `PublicPortfolioPage.tsx`'s existing structure/styling conventions as
reasonable (reuse the same `Badge`/layout primitives from `@/components/ui/`), since this is a
new page type in an otherwise-established design system, not a from-scratch design exercise.
Accept the optional `tierConfig` prop described above for the tier sub-page case.

## Do not touch

- `frontend/src/lib/subdomain.ts`'s `resolveSubdomainRewrite` — explicitly unmodified (see
  "Ambiguity resolved" above).
- `frontend/middleware.ts` — unmodified; the existing `PORTFOLIO_SUBDOMAINS_ENABLED`/
  `PORTFOLIO_SUBDOMAIN_ROOT` env-gated rewrite continues to apply identically to both namespaces
  (a brand-page subdomain still needs the same DNS/wildcard-TLS provisioning as a portfolio
  subdomain — this chunk does not introduce a second, separate subdomain-enablement flag).
- `backend/app/modules/portfolio/` — untouched; `PortfolioProfile.slug`'s uniqueness constraint
  and existing public endpoint are unaffected.
- `machine-1-tenancy-core/04-cors-and-ratelimit-retrofit.md`'s CORS logic — a public brand page
  fetched server-side (Next.js server component, per the existing `/p/[slug]/page.tsx` pattern)
  is not a browser CORS request at all (it's a server-to-server fetch from the Next.js server to
  the backend), so no CORS-related change is needed here — confirm this is actually how
  `backendFetchPublic` works (server-side fetch, not client-side) before assuming, but the
  existing `/p/[slug]/page.tsx` already establishes this is the pattern.
- Any query-filtering/access-control logic anywhere in the backend — `Brand` (and its tier
  config) is presentation-only; this chunk must not introduce any code path that uses
  `signup_brand_id` or a brand slug to filter candidate/recruiter/job data. If a future reader is
  tempted to add "show only this brand's candidates" logic near this code, that is out of scope
  and contradicts the shared-pool model this whole doc set assumes.

## Verification

- Test: a request to `/p/{brand-slug}` where `{brand-slug}` matches an active `Brand` but no
  `PortfolioProfile` renders `BrandLandingPage`.
- Test: a request to `/p/{candidate-slug}` still renders `PublicPortfolioPage` exactly as before
  this chunk (regression check on the existing, unmodified-in-behavior first branch).
- Test: a request to `/p/{unknown-slug}` (matching neither) still 404s.
- Test: `GET /api/brands/public/{slug}` for an `is_active=False` brand 404s (a brand that's
  deactivated shouldn't keep a public landing page live).
- Test: `PublicBrandResponse`'s serialized shape contains no `custom_domain`, `chatbot_config`, or
  other internal-only fields.
- Test: `/b/{slug}/{tier}` renders `BrandLandingPage` with the tier-specific copy when `{tier}`
  matches a key in the brand's `landing_page_tier_config`.
- Test: `/b/{slug}/{tier}` 404s when `{tier}` is not a configured key for that brand (no silent
  fallback to general copy).
- Test: `/b/{slug}` (no tier segment) still renders the brand's general landing page unaffected
  by the tier sub-page addition.
