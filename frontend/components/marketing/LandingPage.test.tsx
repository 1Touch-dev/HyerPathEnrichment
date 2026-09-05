import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LandingPage } from "./LandingPage";

vi.mock("@/components/marketing/TrustBlock", () => ({
  TrustBlock: () => <div>Trust</div>,
  SampleDossierCard: () => <div>Sample dossier</div>,
}));

describe("LandingPage", () => {
  it("preserves configured tiers in every OSINT enrichment CTA", () => {
    render(
      <LandingPage
        config={{
          slug: "research",
          eyebrow: "Research",
          headline: "Public-signal research",
          subheadline: "Use the configured enrichment depth.",
          tiers: ["tier1", "tier3"],
          ctaLabel: "Start research",
          highlights: ["Customer-supplied identifiers"],
        }}
      />,
    );

    expect(screen.getAllByRole("link", { name: "Start research" })).toHaveLength(2);
    for (const link of screen.getAllByRole("link", { name: "Start research" })) {
      expect(link).toHaveAttribute("href", "/osint?tiers=tier1,tier3");
    }
  });
});
