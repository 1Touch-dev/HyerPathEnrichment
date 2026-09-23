import { notFound } from "next/navigation";
import { PersonaLandingPage } from "@/features/marketing";
import { getLandingBySlug } from "@/src/lib/landing-content";

export default function RecruitersPage() {
  const config = getLandingBySlug("recruiters");
  if (!config) notFound();
  return <PersonaLandingPage config={config} />;
}
