import { notFound } from "next/navigation";
import { LandingPage } from "@/components/marketing/LandingPage";
import { getLandingBySlug } from "@/src/lib/landing-content";

export default function SalesPage() {
  const config = getLandingBySlug("sales");
  if (!config) notFound();
  return <LandingPage config={config} />;
}
