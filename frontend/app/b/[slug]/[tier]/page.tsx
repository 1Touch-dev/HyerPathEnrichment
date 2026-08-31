import { notFound } from "next/navigation";
import { adaptPublicBrand } from "@/src/lib/api-adapter";
import { unwrapEnvelopeData } from "@/src/lib/api-envelope";
import { backendFetchPublic } from "@/src/lib/backend-client";
import { getTierCopy, parseBrandLandingConfig } from "@/src/lib/brand-landing-config";
import { BrandLandingPage } from "@/features/brand-pages";

// Brand landings are fetched in the page, not in middleware.
// Do not fetch brands in middleware (frontend/middleware.ts).

export default async function BrandLandingTierPage({
  params,
}: {
  params: Promise<{ slug: string; tier: string }>;
}) {
  const { slug, tier } = await params;

  const response = await backendFetchPublic(`/api/brands/public/${slug}`);
  if (!response.ok) notFound();

  const raw = await response.json();
  const brand = adaptPublicBrand(unwrapEnvelopeData(raw));
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
  const response = await backendFetchPublic(`/api/brands/public/${slug}`);
  if (!response.ok) return { title: "Brand not found" };
  const raw = await response.json();
  const brand = adaptPublicBrand(unwrapEnvelopeData(raw));
  const tierCopy = getTierCopy(parseBrandLandingConfig(brand.landingPageTierConfig), tier);
  if (!tierCopy) return { title: "Brand not found" };
  return { title: brand.name };
}
