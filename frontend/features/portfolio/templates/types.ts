import type {
  PortfolioContent,
  PortfolioSectionKey,
  PortfolioTemplateId,
  PortfolioThemeConfig,
} from "@/src/lib/types";

/** Normalized model shared by preview and public rendering. */
export interface PortfolioRenderModel {
  templateId: PortfolioTemplateId;
  theme: PortfolioThemeConfig;
  content: PortfolioContent;
  sectionVisibility: Record<PortfolioSectionKey, boolean>;
  sectionOrder: PortfolioSectionKey[];
}

export interface PortfolioTemplateProps {
  model: PortfolioRenderModel;
  /** When true, templates may tighten spacing for the studio preview chrome. */
  preview?: boolean;
}

export interface TemplateMeta {
  id: PortfolioTemplateId;
  name: string;
  tagline: string;
  bestFor: string;
}
