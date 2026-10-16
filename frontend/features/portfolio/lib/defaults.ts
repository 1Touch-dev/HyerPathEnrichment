import type {
  PortfolioContent,
  PortfolioRevision,
  PortfolioSectionKey,
  PortfolioThemeConfig,
} from "@/src/lib/types";

export const DEFAULT_SECTION_ORDER: PortfolioSectionKey[] = [
  "about",
  "projects",
  "experience",
  "education",
  "skills",
  "certifications",
  "social",
  "contact",
];

export function defaultSectionVisibility(): Record<PortfolioSectionKey, boolean> {
  return {
    about: true,
    projects: true,
    experience: true,
    education: true,
    skills: true,
    certifications: true,
    social: true,
    contact: true,
  };
}

export function defaultTheme(): PortfolioThemeConfig {
  return { palette: "neutral", accent: null, fontPairing: "sans" };
}

export function emptyContent(): PortfolioContent {
  return {
    displayName: null,
    professionalRole: null,
    location: null,
    headline: null,
    summary: null,
    about: null,
    profileImageUrl: null,
    coverImageUrl: null,
    email: null,
    resumeUrl: null,
    projects: [],
    experience: [],
    education: [],
    skills: [],
    certifications: [],
    socialLinks: [],
  };
}

export function emptyRevision(): PortfolioRevision {
  return {
    templateId: "minimal_professional",
    theme: defaultTheme(),
    content: emptyContent(),
    sectionVisibility: defaultSectionVisibility(),
    sectionOrder: [...DEFAULT_SECTION_ORDER],
  };
}

export function newEntityId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
