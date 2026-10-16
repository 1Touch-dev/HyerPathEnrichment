import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PublicPortfolioPage } from "./PublicPortfolioPage";
import type { PublicPortfolioProfile } from "@/src/lib/types";
import { defaultSectionVisibility, defaultTheme, emptyContent } from "../lib/defaults";

const content = {
  ...emptyContent(),
  displayName: "Jane Doe",
  headline: "Backend Engineer",
  summary: "I build things.",
  about: "I build things.",
  projects: [
    {
      id: "i1",
      title: "My repo",
      description: "A cool project",
      imageUrl: null,
      techStack: ["Python"],
      demoUrl: null,
      repoUrl: "https://github.com/jane/repo",
      displayOrder: 0,
    },
  ],
};

const baseProfile: PublicPortfolioProfile = {
  slug: "jane-doe",
  displayName: "Jane Doe",
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
  templateId: "minimal_professional",
  theme: defaultTheme(),
  content,
  sectionVisibility: defaultSectionVisibility(),
  sectionOrder: [
    "about",
    "projects",
    "experience",
    "education",
    "skills",
    "certifications",
    "social",
    "contact",
  ],
};

describe("PublicPortfolioPage", () => {
  it("renders headline and summary when present", () => {
    render(<PublicPortfolioPage profile={baseProfile} />);
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getAllByText("I build things.").length).toBeGreaterThan(0);
  });

  it("does not render headline or summary when null", () => {
    render(
      <PublicPortfolioPage
        profile={{
          ...baseProfile,
          headline: null,
          summary: null,
          content: { ...content, headline: null, summary: null, about: null },
        }}
      />,
    );
    expect(screen.queryByText("Backend Engineer")).not.toBeInTheDocument();
    expect(screen.queryByText("I build things.")).not.toBeInTheDocument();
  });

  it("renders project repo links with target=_blank", () => {
    render(<PublicPortfolioPage profile={baseProfile} />);
    const link = screen.getByText("Code").closest("a");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAttribute("href", "https://github.com/jane/repo");
  });

  it("renders nothing for projects when empty", () => {
    render(
      <PublicPortfolioPage
        profile={{
          ...baseProfile,
          items: [],
          content: { ...content, projects: [] },
        }}
      />,
    );
    expect(screen.queryByText("My repo")).not.toBeInTheDocument();
  });

  it("uses the selected template data attribute", () => {
    const { container } = render(
      <PublicPortfolioPage profile={{ ...baseProfile, templateId: "developer_dark" }} />,
    );
    expect(container.querySelector('[data-portfolio-template="developer_dark"]')).not.toBeNull();
  });

  it("switches layout for creative showcase without losing project content", () => {
    render(<PublicPortfolioPage profile={{ ...baseProfile, templateId: "creative_showcase" }} />);
    expect(screen.getByText("Featured projects")).toBeInTheDocument();
    expect(screen.getByText("My repo")).toBeInTheDocument();
  });
});
