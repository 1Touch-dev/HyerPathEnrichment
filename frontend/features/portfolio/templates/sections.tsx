import type { PortfolioContent, PortfolioSectionKey } from "@/src/lib/types";
import { isSectionVisible } from "./theme";

export function hasSectionContent(key: PortfolioSectionKey, content: PortfolioContent): boolean {
  switch (key) {
    case "about":
      return Boolean(content.about?.trim() || content.summary?.trim());
    case "projects":
      return content.projects.length > 0;
    case "experience":
      return content.experience.length > 0;
    case "education":
      return content.education.length > 0;
    case "skills":
      return content.skills.length > 0;
    case "certifications":
      return content.certifications.length > 0;
    case "social":
      return content.socialLinks.length > 0;
    case "contact":
      return Boolean(content.email || content.resumeUrl);
    default:
      return false;
  }
}

export function visibleSections(
  order: PortfolioSectionKey[],
  visibility: Record<string, boolean>,
  content: PortfolioContent,
): PortfolioSectionKey[] {
  return order.filter((key) => isSectionVisible(key, visibility, hasSectionContent(key, content)));
}

export function displayNameOf(content: PortfolioContent): string {
  return content.displayName?.trim() || "Portfolio";
}

export function ExternalLink({
  href,
  children,
  className,
  style,
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className} style={style}>
      {children}
    </a>
  );
}
