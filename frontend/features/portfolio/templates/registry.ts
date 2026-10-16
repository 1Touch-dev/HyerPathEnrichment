import type { ComponentType } from "react";
import type { PortfolioTemplateId } from "@/src/lib/types";
import { CreativeShowcase } from "./CreativeShowcase";
import { DeveloperDark } from "./DeveloperDark";
import { ExecutiveElegant } from "./ExecutiveElegant";
import { MinimalProfessional } from "./MinimalProfessional";
import { PersonalStory } from "./PersonalStory";
import type { PortfolioTemplateProps, TemplateMeta } from "./types";

export const TEMPLATE_META: TemplateMeta[] = [
  {
    id: "minimal_professional",
    name: "Minimal Professional",
    tagline: "Clean typography and quiet confidence",
    bestFor: "Students, analysts, consultants",
  },
  {
    id: "creative_showcase",
    name: "Creative Showcase",
    tagline: "Bold visuals and project galleries",
    bestFor: "Designers, marketers, creators",
  },
  {
    id: "developer_dark",
    name: "Developer Dark",
    tagline: "Technical dark theme with stack badges",
    bestFor: "Engineers and builders",
  },
  {
    id: "executive_elegant",
    name: "Executive Elegant",
    tagline: "Corporate polish and career timelines",
    bestFor: "Managers and senior professionals",
  },
  {
    id: "personal_story",
    name: "Personal Story",
    tagline: "Editorial storytelling and journey",
    bestFor: "Career changers and multidisciplinary talent",
  },
];

export const TEMPLATE_COMPONENTS: Record<
  PortfolioTemplateId,
  ComponentType<PortfolioTemplateProps>
> = {
  minimal_professional: MinimalProfessional,
  creative_showcase: CreativeShowcase,
  developer_dark: DeveloperDark,
  executive_elegant: ExecutiveElegant,
  personal_story: PersonalStory,
};

/** Default theme suggestions per template — content is never changed by these. */
export const TEMPLATE_DEFAULT_PALETTE: Record<PortfolioTemplateId, string> = {
  minimal_professional: "neutral",
  creative_showcase: "vibrant",
  developer_dark: "ocean",
  executive_elegant: "slate",
  personal_story: "forest",
};
