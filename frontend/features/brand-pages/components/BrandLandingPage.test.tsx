import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { PublicBrand } from "@/src/lib/types";
import { BrandLandingPage } from "./BrandLandingPage";

function brand(overrides: Partial<PublicBrand> = {}): PublicBrand {
  return {
    name: "Acme",
    slug: "acme",
    landingPageTierConfig: null,
    ...overrides,
  };
}

describe("BrandLandingPage", () => {
  it("renders coming-soon copy and a /register CTA when config is empty", () => {
    render(<BrandLandingPage brand={brand({ landingPageTierConfig: {} })} />);

    expect(screen.getByRole("heading", { name: "Acme" })).toBeInTheDocument();
    expect(screen.getByText("We're launching soon")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Get started" })).toHaveAttribute("href", "/register");
  });

  it("renders general headline and CTA, not coming-soon copy", () => {
    render(
      <BrandLandingPage
        brand={brand({
          landingPageTierConfig: { headline: "Join Acme", cta_label: "Apply now" },
        })}
      />,
    );

    expect(screen.getByRole("heading", { name: "Join Acme" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Apply now" })).toHaveAttribute("href", "/register");
    expect(screen.queryByText("We're launching soon")).not.toBeInTheDocument();
  });

  it("renders tier copy and does not fall back to general headline/CTA", () => {
    render(
      <BrandLandingPage
        brand={brand({
          landingPageTierConfig: {
            headline: "Join Acme",
            cta_label: "Apply now",
            premium: { headline: "Premium desk", cta_label: "Join premium" },
          },
        })}
        tierConfig={{ headline: "Premium desk", ctaLabel: "Join premium" }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Premium desk" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Join premium" })).toHaveAttribute("href", "/register");
    expect(screen.queryByText("Join Acme")).not.toBeInTheDocument();
    expect(screen.queryByText("Apply now")).not.toBeInTheDocument();
    expect(screen.queryByText("We're launching soon")).not.toBeInTheDocument();
  });
});
