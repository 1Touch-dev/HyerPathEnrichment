import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { MatchCard } from "./MatchCard";
import * as client from "../api/client";
import type { JobMatch } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const baseMatch: JobMatch = {
  matchId: "m1",
  jobPostingId: "jp1",
  title: "Senior Engineer",
  company: "Acme",
  location: "Remote",
  remote: true,
  source: "linkedin",
  sourceUrl: "https://example.com/job/1",
  salaryMin: null,
  salaryMax: null,
  salaryCurrency: null,
  overallScore: 87,
  scoreBreakdown: {},
  explanation: "Great fit for your skills.",
  isNew: true,
  viewedAt: null,
  feedback: null,
  createdAt: "2026-01-01T00:00:00Z",
  applyClickedAt: null,
  appliedAt: null,
};

describe("MatchCard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(client, "markMatchViewed").mockResolvedValue(undefined);
    vi.spyOn(client, "submitMatchFeedback").mockResolvedValue(undefined);
    vi.spyOn(client, "markApplied").mockResolvedValue(undefined);
  });

  it("renders the score badge and explanation", () => {
    render(<MatchCard match={baseMatch} />, { wrapper });
    expect(screen.getByText("87/100")).toBeInTheDocument();
    expect(screen.getByText("Great fit for your skills.")).toBeInTheDocument();
  });

  it('renders a "Broader match" badge instead of the score badge when below_similarity_threshold is true', () => {
    const relaxedMatch: JobMatch = {
      ...baseMatch,
      scoreBreakdown: { below_similarity_threshold: true },
    };
    render(<MatchCard match={relaxedMatch} />, { wrapper });
    expect(screen.getByText("Broader match")).toBeInTheDocument();
    expect(screen.queryByText("87/100")).not.toBeInTheDocument();
  });

  it("marks the match viewed on mount when isNew is true", async () => {
    render(<MatchCard match={baseMatch} />, { wrapper });
    await waitFor(() => expect(client.markMatchViewed).toHaveBeenCalledTimes(1));
    expect(client.markMatchViewed).toHaveBeenCalledWith("m1");
  });

  it("does not mark the match viewed when isNew is false", async () => {
    render(<MatchCard match={{ ...baseMatch, isNew: false }} />, { wrapper });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(client.markMatchViewed).not.toHaveBeenCalled();
  });

  it("submits positive feedback with correct args on click", async () => {
    render(<MatchCard match={baseMatch} />, { wrapper });
    fireEvent.click(screen.getByLabelText("Good match"));
    await waitFor(() => expect(client.submitMatchFeedback).toHaveBeenCalledWith("m1", "up"));
  });

  it("submits negative feedback with correct args on click", async () => {
    render(<MatchCard match={baseMatch} />, { wrapper });
    fireEvent.click(screen.getByLabelText("Not a good match"));
    await waitFor(() => expect(client.submitMatchFeedback).toHaveBeenCalledWith("m1", "down"));
  });

  it("renders an Apply link with rel=noopener noreferrer, target=_blank, and the correct href", () => {
    render(<MatchCard match={baseMatch} />, { wrapper });
    const applyLink = screen.getByRole("link", { name: "Apply" });
    expect(applyLink).toHaveAttribute("href", "/api/matches/m1/apply-redirect");
    expect(applyLink).toHaveAttribute("target", "_blank");
    expect(applyLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("Mark-as-applied checkbox is unchecked when appliedAt is null", () => {
    render(<MatchCard match={baseMatch} />, { wrapper });
    expect(screen.getByRole("checkbox", { name: "Mark as applied" })).not.toBeChecked();
  });

  it("Mark-as-applied checkbox is checked when appliedAt is set", () => {
    render(<MatchCard match={{ ...baseMatch, appliedAt: "2026-01-02T00:00:00Z" }} />, { wrapper });
    expect(screen.getByRole("checkbox", { name: "Mark as applied" })).toBeChecked();
  });

  it("calls markApplied with applied=true when the Mark-as-applied checkbox is toggled on", async () => {
    render(<MatchCard match={baseMatch} />, { wrapper });
    fireEvent.click(screen.getByRole("checkbox", { name: "Mark as applied" }));
    await waitFor(() => expect(client.markApplied).toHaveBeenCalledWith("m1", true));
  });

  it("calls markApplied with applied=false when the Mark-as-applied checkbox is toggled off", async () => {
    render(<MatchCard match={{ ...baseMatch, appliedAt: "2026-01-02T00:00:00Z" }} />, { wrapper });
    fireEvent.click(screen.getByRole("checkbox", { name: "Mark as applied" }));
    await waitFor(() => expect(client.markApplied).toHaveBeenCalledWith("m1", false));
  });
});
