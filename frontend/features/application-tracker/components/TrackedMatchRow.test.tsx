import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { TrackedMatchRow } from "./TrackedMatchRow";
import * as trackerClient from "../api/client";
import * as matchingClient from "@/features/job-matching/api/client";
import type { TrackedMatch } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const baseMatch: TrackedMatch = {
  matchId: "m1",
  jobPostingId: "jp1",
  title: "Senior Engineer",
  company: "Acme",
  location: "Remote",
  remote: true,
  sourceUrl: "https://example.com/job/1",
  overallScore: 87,
  applicationStatus: "new",
  applyClickedAt: null,
  appliedAt: null,
  statusUpdatedAt: null,
  createdAt: "2026-01-01T00:00:00Z",
  nextInterviewAt: null,
};

describe("TrackedMatchRow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(trackerClient, "updateApplicationStatus").mockResolvedValue(baseMatch);
    vi.spyOn(matchingClient, "markApplied").mockResolvedValue(undefined);
  });

  it("renders the score when overallScore is present", () => {
    render(<TrackedMatchRow match={baseMatch} />, { wrapper });
    expect(screen.getByText("87/100")).toBeInTheDocument();
  });

  it('renders "—" with the manual-entry tooltip when overallScore is null', () => {
    render(<TrackedMatchRow match={{ ...baseMatch, overallScore: null }} />, { wrapper });
    const placeholder = screen.getByText("—");
    expect(placeholder).toBeInTheDocument();
    expect(placeholder).toHaveAttribute("title", "Manually added — no match score");
  });

  it.each([
    ["new", "New", "bg-gray-100"],
    ["applied", "Applied", "bg-blue-100"],
    ["replied", "Replied", "bg-purple-100"],
    ["interview", "Interview", "bg-amber-100"],
    ["offer", "Offer", "bg-green-100"],
    ["rejected", "Rejected", "bg-red-100"],
  ] as const)(
    "renders the %s status badge with label %s and color class %s",
    (status, label, colorClass) => {
      render(<TrackedMatchRow match={{ ...baseMatch, applicationStatus: status }} />, { wrapper });
      const badges = screen.getAllByText(label);
      expect(badges.some((el) => el.className.includes(colorClass))).toBe(true);
    },
  );

  it("renders an Apply link pointing at the apply-redirect BFF route", () => {
    render(<TrackedMatchRow match={baseMatch} />, { wrapper });
    const applyLink = screen.getByRole("link", { name: "Apply" });
    expect(applyLink).toHaveAttribute("href", "/api/matches/m1/apply-redirect");
  });

  it("renders no interview chip when nextInterviewAt is null", () => {
    render(<TrackedMatchRow match={baseMatch} />, { wrapper });
    expect(screen.queryByText(/Interview:/)).not.toBeInTheDocument();
  });
});
