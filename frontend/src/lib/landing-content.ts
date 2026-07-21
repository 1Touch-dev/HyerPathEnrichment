import { RequestedTier } from "@/src/lib/types";

export type LandingConfig = {
  slug: string;
  eyebrow: string;
  headline: string;
  subheadline: string;
  tiers: RequestedTier[];
  ctaLabel: string;
  highlights: string[];
};

export const landingPages: LandingConfig[] = [
  {
    slug: "recruiters",
    eyebrow: "For recruiters",
    headline: "Identity, GitHub, and personal site signals in one dossier",
    subheadline:
      "Start from a LinkedIn URL or username and let Tier 1–3 correlate photo assets, handles, and verified contact channels.",
    tiers: ["tier1", "tier2", "tier3"],
    ctaLabel: "Open console with recruiter tiers",
    highlights: [
      "LinkedIn photo capture with confidence scoring",
      "Cross-platform handle discovery",
      "Verified email intelligence for outreach",
    ],
  },
  {
    slug: "candidates",
    eyebrow: "For candidates",
    headline: "Jobs across every board, correlated to your profile",
    subheadline:
      "Tier 4 job search plus Tier 2 username discovery helps you monitor listings and public presence from one intake form.",
    tiers: ["tier4", "tier2"],
    ctaLabel: "Open console with candidate tiers",
    highlights: [
      "Multi-board job aggregation",
      "Username-based social footprint",
      "Self-hosted — you own the data",
    ],
  },
  {
    slug: "sales",
    eyebrow: "For sales teams",
    headline: "Work email and coworker graph from a single identifier",
    subheadline:
      "Tier 3 deep OSINT surfaces verified emails, GitHub coworkers, and organization signals for account research.",
    tiers: ["tier3"],
    ctaLabel: "Open console with sales tiers",
    highlights: [
      "Verified email discovery",
      "Coworker and org correlation",
      "Ops-grade confidence breakdown",
    ],
  },
  {
    slug: "investors",
    eyebrow: "For investors",
    headline: "Founder due diligence across all enrichment tiers",
    subheadline:
      "Run the full pipeline — photo, handles, OSINT, and business intelligence — from one async job.",
    tiers: ["tier1", "tier2", "tier3", "tier4"],
    ctaLabel: "Open console with full tiers",
    highlights: [
      "Full four-tier pipeline",
      "Raw JSON for audit trails",
      "Suppression-aware compliance path",
    ],
  },
  {
    slug: "journalists",
    eyebrow: "For journalists",
    headline: "Contact channel discovery with source attribution",
    subheadline:
      "Tier 2 and Tier 3 combine public handle discovery with verified email intelligence and cited sources.",
    tiers: ["tier2", "tier3"],
    ctaLabel: "Open console with journalist tiers",
    highlights: [
      "Handle discovery across platforms",
      "Verified email status labels",
      "Source list for every signal",
    ],
  },
];

export const hubAudiences = landingPages.map((page) => ({
  slug: page.slug,
  eyebrow: page.eyebrow,
  headline: page.headline.split(".")[0] + ".",
  tiers: page.tiers,
}));

export function getLandingBySlug(slug: string): LandingConfig | undefined {
  return landingPages.find((page) => page.slug === slug);
}

export const tierDescriptions: Record<RequestedTier, string> = {
  tier1: "LinkedIn photo capture via browser pipeline",
  tier2: "Username discovery across public platforms",
  tier3: "Deep OSINT — emails, GitHub, coworkers",
  tier4: "Job listings and local business intelligence",
};
