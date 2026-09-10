import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  ShellPage,
  ShellPageHeader,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
  ShellSection,
} from "./ShellPage";

describe("ShellPage contracts", () => {
  it("applies product-specific framing metadata", () => {
    render(
      <>
        <ShellPage product="candidate" data-testid="candidate-page">
          Candidate content
        </ShellPage>
        <ShellPage product="desk" width="full" data-testid="desk-page">
          Desk content
        </ShellPage>
      </>,
    );

    expect(screen.getByTestId("candidate-page")).toHaveAttribute("data-shell-product", "candidate");
    expect(screen.getByTestId("candidate-page")).toHaveAttribute(
      "data-shell-density",
      "comfortable",
    );
    expect(screen.getByTestId("candidate-page")).toHaveClass("max-w-6xl");

    expect(screen.getByTestId("desk-page")).toHaveAttribute("data-shell-width", "full");
    expect(screen.getByTestId("desk-page")).toHaveClass("max-w-none");
  });

  it("composes reusable header and section wrappers for downstream lanes", () => {
    render(
      <div>
        <ShellPageHeader data-testid="header">
          <ShellPageHeaderContent>
            <ShellPageHeaderEyebrow>OSINT</ShellPageHeaderEyebrow>
            <ShellPageHeaderTitle>Look up</ShellPageHeaderTitle>
            <ShellPageHeaderDescription>Evidence-first intake.</ShellPageHeaderDescription>
          </ShellPageHeaderContent>
        </ShellPageHeader>
        <ShellSection data-testid="section" surface="elevated">
          Shell section
        </ShellSection>
      </div>,
    );

    expect(screen.getByTestId("header")).toHaveClass("rounded-[1.25rem]", "shadow-panel");
    expect(screen.getByText("Look up")).toBeInTheDocument();
    expect(screen.getByTestId("section")).toHaveAttribute("data-shell-surface", "elevated");
    expect(screen.getByTestId("section")).toHaveClass("app-surface-elevated");
  });
});
