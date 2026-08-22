# Post-Tenancy Features, Chunk 2 — Brand Landing Pages

## Depends on

`post-tenancy-retrofit/04-tenant-isolation-test-suite.md` green on real Postgres.
`machine-1-tenancy-core`'s `Organization` model (`slug`, `custom_origin` columns).

## Goal

Give each placement agency (`Organization`) a public, branded landing page — e.g.
`acme-staffing.hyrepath.com` — showcasing the agency (not an individual candidate). This is the
**org-level** counterpart to the existing **candidate-level** public portfolio page
(`frontend/app/p/[slug]/page.tsx`, backed by `GET /api/portfolio/public/{slug}`), and reuses the
exact same subdomain-rewrite mechanism, extended to also recognize org slugs.

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
org slug," and the target route `/p/[slug]` always resolves against
`GET /api/portfolio/public/{slug}` (candidates only). This chunk must decide how an org slug and
a candidate slug are disambiguated, since both now live under the same subdomain scheme and
`Organization.slug` (`machine-1-tenancy-core/02`) and `PortfolioProfile.slug`
(`backend/app/modules/portfolio/models.py` line 23) are **separate, independently-unique
columns today** — a collision (an org and a candidate both choosing slug `"acme"`) is possible
and must be handled, not assumed away.

## Ambiguity resolved: separate route prefix, not slug-uniqueness enforcement

**Do not** attempt to enforce global slug uniqueness across `Organization.slug` and
`PortfolioProfile.slug` (that would require a cross-module unique constraint or an application-
level check on every candidate portfolio-slug write, coupling two modules that are otherwise
intentionally decoupled). Instead, give org brand pages their **own** route prefix, `/b/{slug}`
(brand), parallel to but distinct from `/p/{slug}` (portfolio) — this makes the two slug
namespaces genuinely independent (a collision between an org slug and a candidate slug is
harmless; they resolve to different pages) and requires no change to
`portfolio_profiles.slug`'s existing uniqueness constraint.

## Files to create

- `frontend/app/b/[slug]/page.tsx`
- `frontend/features/brand-pages/components/BrandLandingPage.tsx`
- `frontend/features/brand-pages/index.ts`
- `backend/app/modules/orgs/public_schemas.py` (or add to the existing
  `backend/app/modules/orgs/schemas.py` from `machine-1-tenancy-core/02` if that file is small
  enough that a second file would be unnecessary fragmentation — implementer's judgment, but
  keep public/authenticated-facing schemas clearly separated either via file or a clear naming
  convention, matching how `portfolio/schemas.py` separates `PortfolioProfileResponse` from
  `PublicPortfolioResponse`)
- `backend/app/modules/orgs/public_router.py`

## `resolveSubdomainRewrite` retrofit (`frontend/src/lib/subdomain.ts`)

The function needs to disambiguate which namespace a subdomain belongs to. Since the pure-logic
function has no DB access (by design — "no I/O" is implied by its existing unit-testability
without a real `NextRequest`/Edge runtime, per its module docstring), **the disambiguation cannot
happen inside `resolveSubdomainRewrite` itself.** Two options:

- **(a)** Change the function's return type from `string | null` to a tagged union,
  `{ kind: "portfolio" | "brand"; slug: string } | null`, and have the **caller**
  (`middleware.ts`) decide the rewrite path — but the caller still has no DB access at the Edge
  runtime layer to know whether `slug` belongs to an org or a candidate.
- **(b)** Keep `resolveSubdomainRewrite` exactly as-is (returning `/p/${slug}` always, unmodified
  — **do not change this function's existing signature or behavior**, since
  `frontend/features/portfolio/components/PublicPortfolioPage.test.tsx`-adjacent tests and any
  existing consumer depend on its current contract), and instead make **`/p/[slug]/page.tsx`
  itself** the disambiguation point: it already calls `GET /api/portfolio/public/{slug}` and
  calls `notFound()` on a non-OK response (see `frontend/app/p/[slug]/page.tsx` lines 10-11) —
  extend it to, on a 404 from the portfolio endpoint, fall through to a **second** check against
  the new org-brand public endpoint (`GET /api/orgs/public/{slug}`), rendering
  `BrandLandingPage` instead if that succeeds, and only calling `notFound()` if *both* miss.

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

  // Falls through to the org-brand namespace on a portfolio miss — see
  // post-tenancy-features/02-brand-landing-pages.md for why this dual-check lives
  // here rather than in middleware.ts/subdomain.ts (no DB access at the Edge layer).
  const brandResponse = await backendFetchPublic(`/api/orgs/public/${slug}`);
  if (!brandResponse.ok) notFound();

  const brandRaw = await brandResponse.json();
  const org = adaptPublicOrganization(unwrapEnvelopeData(brandRaw));
  return <BrandLandingPage organization={org} />;
}
```

(`adaptPublicOrganization` — new adapter function in `frontend/src/lib/api-adapter.ts`, following
the exact existing pattern of `adaptPublicPortfolioProfile` in that same file; read that
function's current implementation before writing the new one so field-mapping conventions match.)

Update `generateMetadata` in the same file with the identical fallback shape.

## `backend/app/modules/orgs/public_router.py`

```python
public_router = APIRouter(prefix="/api/orgs", tags=["orgs-public"], route_class=EnvelopeAPIRoute)

@public_router.get("/public/{slug}", response_model=PublicOrganizationResponse)
async def get_public_organization(
    slug: str, db: AsyncSession = Depends(get_db_session)
) -> PublicOrganizationResponse:
    """Unauthenticated — mirrors portfolio/router.py's get_public_profile exactly:
    no CurrentUser dependency, 404 on missing/inactive org. This is the endpoint the
    public /p/{slug} page's brand-page fallback (frontend/app/p/[slug]/page.tsx) calls."""
    org = await repository.get_organization_by_slug(db, slug)
    if org is None or not org.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return PublicOrganizationResponse(name=org.name, slug=org.slug, ...)
```

`PublicOrganizationResponse` must **not** leak `custom_origin`, internal ids beyond what's needed
for display, or any recruiter/candidate PII — it is a public, unauthenticated response, same
privacy bar as `PublicPortfolioResponse` already sets for candidate data.

Register `public_router` in `backend/app/main.py` next to the existing portfolio public router
registration.

## `frontend/features/brand-pages/components/BrandLandingPage.tsx`

A simple, brand-appropriate page — company name, headline/description copy, and (if this
effort's later scope wants it — flag as a follow-up, not required for this chunk's minimum) a
call-to-action linking to a candidate application or contact form. Keep the initial version as
minimal and close to `PublicPortfolioPage.tsx`'s existing structure/styling conventions as
reasonable (reuse the same `Badge`/layout primitives from `@/components/ui/`), since this is a
new page type in an otherwise-established design system, not a from-scratch design exercise.

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

## Verification

- Test: a request to `/p/{org-slug}` where `{org-slug}` matches an active `Organization` but no
  `PortfolioProfile` renders `BrandLandingPage`.
- Test: a request to `/p/{candidate-slug}` still renders `PublicPortfolioPage` exactly as before
  this chunk (regression check on the existing, unmodified-in-behavior first branch).
- Test: a request to `/p/{unknown-slug}` (matching neither) still 404s.
- Test: `GET /api/orgs/public/{slug}` for an `is_active=False` org 404s (an agency that's
  deactivated its account shouldn't keep a public brand page live).
- Test: `PublicOrganizationResponse`'s serialized shape contains no `custom_origin` or other
  internal-only fields.
