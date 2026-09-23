import { notFound } from "next/navigation";
import { PersonaLandingPage } from "@/features/marketing";
import { getLandingBySlug } from "@/src/lib/landing-content";

export default function SalesPage() {
  const config = getLandingBySlug("sales");
  if (!config) notFound();
  return <PersonaLandingPage config={config} />;
}
