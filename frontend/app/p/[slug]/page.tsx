import { notFound } from "next/navigation";
import { fetchPublicBrand } from "@/src/lib/fetch-public-brand";
import { fetchPublicPortfolio } from "@/src/lib/fetch-public-portfolio";
import { BrandLandingPage } from "@/features/brand-pages";
import { PublicPortfolioPage } from "@/features/portfolio";

export default async function PublicSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  // Disambiguation lives here because resolveSubdomainRewrite is I/O-free and always
  // returns /p/${slug} — do not add a DB lookup in middleware.ts.
  // Portfolio wins on slug collision. A brand with the same slug is unreachable via
  // subdomain rewrite. Do not "fix" this to brand-first.

  const profile = await fetchPublicPortfolio(slug);
  if (profile) {
    return <PublicPortfolioPage profile={profile} />;
  }

  const brand = await fetchPublicBrand(slug);
  if (!brand) notFound();

  return <BrandLandingPage brand={brand} />;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  // Same dual-check as the page: portfolio first, then brand. See page comments —
  // do not add a DB lookup in middleware.ts; do not invert to brand-first.

  const profile = await fetchPublicPortfolio(slug);
  if (profile) {
    return {
      title: profile.headline ? `${profile.headline} — Portfolio` : "Portfolio",
    };
  }

  const brand = await fetchPublicBrand(slug);
  if (brand) {
    return { title: brand.name };
  }

  return { title: "Not found" };
}
