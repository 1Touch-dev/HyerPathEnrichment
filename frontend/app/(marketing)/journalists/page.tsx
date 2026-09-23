import { notFound } from "next/navigation";
import { PersonaLandingPage } from "@/features/marketing";
import { getLandingBySlug } from "@/src/lib/landing-content";

export default function JournalistsPage() {
  const config = getLandingBySlug("journalists");
  if (!config) notFound();
  return <PersonaLandingPage config={config} />;
}
