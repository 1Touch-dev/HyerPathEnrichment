import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { JdPracticeEntryCard } from "./JdPracticeEntryCard";

describe("JdPracticeEntryCard", () => {
  it("links to the practice route with the correct jobMatchId query param", () => {
    render(<JdPracticeEntryCard jobMatchId="match-123" />);
    const link = screen.getByRole("link", { name: "Start practice" });
    expect(link).toHaveAttribute("href", "/app/practice?jobMatchId=match-123");
  });

  it("renders unconditionally regardless of application status (not gated to 'interview')", () => {
    render(<JdPracticeEntryCard jobMatchId="match-456" />);
    expect(screen.getByText("Practice for this job")).toBeInTheDocument();
  });
});
