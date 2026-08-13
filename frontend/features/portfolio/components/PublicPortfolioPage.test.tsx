import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PublicPortfolioPage } from "./PublicPortfolioPage";
import type { PublicPortfolioProfile } from "@/src/lib/types";

const baseProfile: PublicPortfolioProfile = {
  slug: "jane-doe",
  headline: "Backend Engineer",
  summary: "I build things.",
  items: [
    {
      itemId: "i1",
      itemType: "github_repo",
      title: "My repo",
      description: "A cool project",
      url: "https://github.com/jane/repo",
      displayOrder: 0,
    },
  ],
};

describe("PublicPortfolioPage", () => {
  it("renders headline and summary when present", () => {
    render(<PublicPortfolioPage profile={baseProfile} />);
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("I build things.")).toBeInTheDocument();
  });

  it("does not render headline or summary when null", () => {
    render(<PublicPortfolioPage profile={{ ...baseProfile, headline: null, summary: null }} />);
    expect(screen.queryByText("Backend Engineer")).not.toBeInTheDocument();
    expect(screen.queryByText("I build things.")).not.toBeInTheDocument();
  });

  it("renders each item link with target=_blank and rel=noopener noreferrer", () => {
    render(<PublicPortfolioPage profile={baseProfile} />);
    const link = screen.getByText("My repo").closest("a");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAttribute("href", "https://github.com/jane/repo");
  });

  it("falls back to the raw item type string for unknown types instead of crashing", () => {
    const profile: PublicPortfolioProfile = {
      ...baseProfile,
      items: [
        {
          ...baseProfile.items[0],
          // @ts-expect-error — deliberately testing an unmapped raw value.
          itemType: "some_unknown_type",
        },
      ],
    };
    render(<PublicPortfolioPage profile={profile} />);
    expect(screen.getByText("some_unknown_type")).toBeInTheDocument();
  });

  it("renders nothing in the items section when there are no items", () => {
    render(<PublicPortfolioPage profile={{ ...baseProfile, items: [] }} />);
    expect(screen.queryByText("My repo")).not.toBeInTheDocument();
  });
});
