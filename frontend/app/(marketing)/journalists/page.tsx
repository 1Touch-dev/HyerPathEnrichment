import { notFound } from "next/navigation";
import { LandingPage } from "@/components/marketing/LandingPage";
import { getLandingBySlug } from "@/src/lib/landing-content";

export default function JournalistsPage() {
  const config = getLandingBySlug("journalists");
  if (!config) notFound();
  return <LandingPage config={config} />;
}
