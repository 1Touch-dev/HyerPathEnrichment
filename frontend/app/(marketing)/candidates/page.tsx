import { notFound } from "next/navigation";
import { PersonaLandingPage } from "@/features/marketing";
import { getLandingBySlug } from "@/src/lib/landing-content";

export default function CandidatesPage() {
  const config = getLandingBySlug("candidates");
  if (!config) notFound();
  return <PersonaLandingPage config={config} />;
}
