import type { PublicPortfolioProfile } from "@/src/lib/types";
import { PortfolioRenderer } from "../templates/PortfolioRenderer";

interface PublicPortfolioPageProps {
  profile: PublicPortfolioProfile;
}

export function PublicPortfolioPage({ profile }: PublicPortfolioPageProps) {
  return (
    <PortfolioRenderer
      model={{
        templateId: profile.templateId,
        theme: profile.theme,
        content: profile.content,
        sectionVisibility: profile.sectionVisibility,
        sectionOrder: profile.sectionOrder,
      }}
    />
  );
}
