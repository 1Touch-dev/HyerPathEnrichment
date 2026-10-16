import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PortfolioRenderer } from "./PortfolioRenderer";
import { defaultSectionVisibility, defaultTheme, emptyContent } from "../lib/defaults";
import type { PortfolioTemplateId } from "@/src/lib/types";

const content = {
  ...emptyContent(),
  displayName: "Alex Rivera",
  headline: "Building things that matter",
  summary: "Engineer and maker",
  about: "I care about craft.",
  professionalRole: "Backend Engineer",
  projects: [
    {
      id: "p1",
      title: "API Platform",
      description: "Scalable APIs",
      imageUrl: null,
      techStack: ["Python", "FastAPI"],
      demoUrl: "https://example.com",
      repoUrl: "https://github.com/alex/api",
      displayOrder: 0,
    },
  ],
  skills: [{ id: "s1", name: "Python", category: null, level: null, displayOrder: 0 }],
  experience: [
    {
      id: "e1",
      company: "Acme",
      title: "Engineer",
      location: null,
      startDate: "2022",
      endDate: null,
      isCurrent: true,
      description: "Shipped platforms",
      achievements: [],
      displayOrder: 0,
    },
  ],
};

function model(templateId: PortfolioTemplateId) {
  return {
    templateId,
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
    ] as Array<
      | "about"
      | "projects"
      | "experience"
      | "education"
      | "skills"
      | "certifications"
      | "social"
      | "contact"
    >,
  };
}

describe("PortfolioRenderer", () => {
  it.each([
    ["minimal_professional", "Selected work"],
    ["creative_showcase", "Featured projects"],
    ["developer_dark", "// projects"],
    ["executive_elegant", "Selected initiatives"],
    ["personal_story", "Work I'm proud of"],
  ] as const)("renders distinct chrome for %s", (templateId, marker) => {
    render(<PortfolioRenderer model={model(templateId)} />);
    expect(screen.getByText(marker)).toBeInTheDocument();
    expect(screen.getByText("API Platform")).toBeInTheDocument();
  });

  it("preserves content when template id changes", () => {
    const { rerender } = render(<PortfolioRenderer model={model("minimal_professional")} />);
    expect(screen.getByText("API Platform")).toBeInTheDocument();
    rerender(<PortfolioRenderer model={model("executive_elegant")} />);
    expect(screen.getByText("API Platform")).toBeInTheDocument();
    expect(screen.getByText("Experience")).toBeInTheDocument();
  });

  it("hides empty optional sections", () => {
    render(
      <PortfolioRenderer
        model={{
          ...model("minimal_professional"),
          content: { ...content, education: [], certifications: [], socialLinks: [] },
        }}
      />,
    );
    expect(screen.queryByText("Education")).not.toBeInTheDocument();
    expect(screen.queryByText("Certifications")).not.toBeInTheDocument();
  });
});
