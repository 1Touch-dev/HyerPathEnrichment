import { notFound } from "next/navigation";
import { adaptPublicPortfolioProfile } from "@/src/lib/api-adapter";
import { backendFetchPublic } from "@/src/lib/backend-client";
import { unwrapEnvelopeData } from "@/src/lib/api-envelope";
import { PublicPortfolioPage } from "@/features/portfolio";

export default async function PublicSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  const response = await backendFetchPublic(`/api/portfolio/public/${slug}`);
  if (!response.ok) notFound();

  const raw = await response.json();
  const profile = adaptPublicPortfolioProfile(unwrapEnvelopeData(raw));

  return <PublicPortfolioPage profile={profile} />;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const response = await backendFetchPublic(`/api/portfolio/public/${slug}`);
  if (!response.ok) return { title: "Portfolio not found" };
  const raw = await response.json();
  const backendProfile = unwrapEnvelopeData<{ headline: string | null }>(raw);
  return { title: backendProfile.headline ? `${backendProfile.headline} — Portfolio` : "Portfolio" };
}
