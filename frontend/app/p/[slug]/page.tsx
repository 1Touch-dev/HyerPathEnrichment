import { notFound } from "next/navigation";
import { adaptPublicBrand, adaptPublicPortfolioProfile } from "@/src/lib/api-adapter";
import { unwrapEnvelopeData } from "@/src/lib/api-envelope";
import { backendFetchPublic } from "@/src/lib/backend-client";
import { BrandLandingPage } from "@/features/brand-pages";
import { PublicPortfolioPage } from "@/features/portfolio";

export default async function PublicSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  // Disambiguation lives here because resolveSubdomainRewrite is I/O-free and always
  // returns /p/${slug} — do not add a DB lookup in middleware.ts.
  // Portfolio wins on slug collision. A brand with the same slug is unreachable via
  // subdomain rewrite. Do not "fix" this to brand-first.

  const portfolioResponse = await backendFetchPublic(`/api/portfolio/public/${slug}`);
  if (portfolioResponse.ok) {
    const raw = await portfolioResponse.json();
    const profile = adaptPublicPortfolioProfile(unwrapEnvelopeData(raw));
    return <PublicPortfolioPage profile={profile} />;
  }

  const brandResponse = await backendFetchPublic(`/api/brands/public/${slug}`);
  if (!brandResponse.ok) notFound();

  const raw = await brandResponse.json();
  const brand = adaptPublicBrand(unwrapEnvelopeData(raw));
  return <BrandLandingPage brand={brand} />;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  // Same dual-check as the page: portfolio first, then brand. See page comments —
  // do not add a DB lookup in middleware.ts; do not invert to brand-first.

  const portfolioResponse = await backendFetchPublic(`/api/portfolio/public/${slug}`);
  if (portfolioResponse.ok) {
    const raw = await portfolioResponse.json();
    const backendProfile = unwrapEnvelopeData<{ headline: string | null }>(raw);
    return {
      title: backendProfile.headline ? `${backendProfile.headline} — Portfolio` : "Portfolio",
    };
  }

  const brandResponse = await backendFetchPublic(`/api/brands/public/${slug}`);
  if (brandResponse.ok) {
    const raw = await brandResponse.json();
    const brand = adaptPublicBrand(unwrapEnvelopeData(raw));
    return { title: brand.name };
  }

  return { title: "Not found" };
}
