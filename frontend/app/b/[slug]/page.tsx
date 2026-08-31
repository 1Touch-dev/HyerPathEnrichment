import { notFound } from "next/navigation";
import { adaptPublicBrand } from "@/src/lib/api-adapter";
import { unwrapEnvelopeData } from "@/src/lib/api-envelope";
import { backendFetchPublic } from "@/src/lib/backend-client";
import { BrandLandingPage } from "@/features/brand-pages";

// Brand landings are fetched in the page, not in middleware.
// Do not fetch brands in middleware (frontend/middleware.ts).

export default async function BrandLandingSlugPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  const response = await backendFetchPublic(`/api/brands/public/${slug}`);
  if (!response.ok) notFound();

  const raw = await response.json();
  const brand = adaptPublicBrand(unwrapEnvelopeData(raw));

  return <BrandLandingPage brand={brand} />;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const response = await backendFetchPublic(`/api/brands/public/${slug}`);
  if (!response.ok) return { title: "Brand not found" };
  const raw = await response.json();
  const brand = adaptPublicBrand(unwrapEnvelopeData(raw));
  return { title: brand.name };
}
