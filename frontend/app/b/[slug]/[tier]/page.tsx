import { notFound } from "next/navigation";
import { getTierCopy, parseBrandLandingConfig } from "@/src/lib/brand-landing-config";
import { fetchPublicBrand } from "@/src/lib/fetch-public-brand";
import { BrandLandingPage } from "@/features/brand-pages";

// Brand landings are fetched in the page, not in middleware.
// Do not fetch brands in middleware (frontend/middleware.ts).

export default async function BrandLandingTierPage({
  params,
}: {
  params: Promise<{ slug: string; tier: string }>;
}) {
  const { slug, tier } = await params;

  const brand = await fetchPublicBrand(slug);
  if (!brand) notFound();

  const tierCopy = getTierCopy(parseBrandLandingConfig(brand.landingPageTierConfig), tier);
  if (!tierCopy) notFound();

  return <BrandLandingPage brand={brand} tierConfig={tierCopy} />;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string; tier: string }>;
}) {
  const { slug, tier } = await params;
  const brand = await fetchPublicBrand(slug);
  if (!brand) return { title: "Brand not found" };
  const tierCopy = getTierCopy(parseBrandLandingConfig(brand.landingPageTierConfig), tier);
  if (!tierCopy) return { title: "Brand not found" };
  return { title: brand.name };
}
