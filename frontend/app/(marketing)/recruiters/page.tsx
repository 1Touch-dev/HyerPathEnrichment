import { notFound } from "next/navigation";
import { LandingPage } from "@/components/marketing/LandingPage";
import { getLandingBySlug } from "@/src/lib/landing-content";

export default function RecruitersPage() {
  const config = getLandingBySlug("recruiters");
  if (!config) notFound();
  return <LandingPage config={config} />;
}
