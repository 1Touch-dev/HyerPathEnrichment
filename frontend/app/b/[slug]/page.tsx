import { notFound } from "next/navigation";
import { fetchPublicBrand } from "@/src/lib/fetch-public-brand";
import { BrandLandingPage } from "@/features/brand-pages";

// Brand landings are fetched in the page, not in middleware.
// Do not fetch brands in middleware (frontend/middleware.ts).

export default async function BrandLandingSlugPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  const brand = await fetchPublicBrand(slug);
  if (!brand) notFound();

  return <BrandLandingPage brand={brand} />;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const brand = await fetchPublicBrand(slug);
  if (!brand) return { title: "Brand not found" };
  return { title: brand.name };
}
