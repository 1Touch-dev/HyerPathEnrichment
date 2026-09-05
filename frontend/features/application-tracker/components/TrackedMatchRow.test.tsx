import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { TrackedMatchRow } from "./TrackedMatchRow";
import { AppShellAccessProvider } from "@/components/layout/app-shell-access";
import * as trackerClient from "../api/client";
import * as matchingClient from "@/features/job-matching/api/client";
import * as useInterviewScheduleHooks from "@/features/interview-scheduling/hooks/useInterviewSchedule";
import type { TrackedMatch } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <AppShellAccessProvider candidateMutationAccess="allowed">
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </AppShellAccessProvider>
  );
}

function restrictedWrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <AppShellAccessProvider candidateMutationAccess="impersonating">
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </AppShellAccessProvider>
  );
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
    vi.spyOn(matchingClient, "getApplyRedirectUrl");
    // InterviewScheduleCard (Module D) is only rendered when applicationStatus ===
    // "interview"; stub its query so those rows don't trigger a real network call.
    vi.spyOn(useInterviewScheduleHooks, "useInterviewSchedule").mockReturnValue({
      data: null,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useInterviewScheduleHooks.useInterviewSchedule>);
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

  it("does not expose the tracked Apply destination during restricted Candidate access", () => {
    render(<TrackedMatchRow match={baseMatch} />, { wrapper: restrictedWrapper });

    const applyLink = screen.getByRole("link", { name: "Apply" });
    expect(applyLink).toHaveAttribute("aria-disabled", "true");
    expect(applyLink).not.toHaveAttribute("href");
  });

  describe("manual-entry Apply affordance degradation (Module F, §10.7-8)", () => {
    const manualMatch: TrackedMatch = {
      ...baseMatch,
      overallScore: null,
      sourceUrl: "https://startup.example.com/careers/growth-marketer",
    };

    it("renders a plain link to sourceUrl (not the redirect-tracked Apply button) for a manual row with a sourceUrl", () => {
      render(<TrackedMatchRow match={manualMatch} />, { wrapper });

      const applyLink = screen.getByRole("link", { name: "Apply" });
      // Points straight at the candidate-provided URL, not Module B's apply-redirect
      // BFF route — a manual entry has no job_posting_id for that endpoint to key off.
      expect(applyLink).toHaveAttribute("href", manualMatch.sourceUrl);
      expect(applyLink).not.toHaveAttribute("href", "/api/matches/m1/apply-redirect");
      // If the degradation logic were removed and this row fell through to the
      // real-posting branch, getApplyRedirectUrl would be called to build the href —
      // confirm it never was, rather than only asserting on the resulting href string.
      expect(matchingClient.getApplyRedirectUrl).not.toHaveBeenCalled();
    });

    it("renders no Apply affordance at all for a manual row without a sourceUrl", () => {
      render(<TrackedMatchRow match={{ ...manualMatch, sourceUrl: null }} />, { wrapper });

      // Distinct from the real-posting case (which always renders a link named
      // "Apply") and from the manual-with-sourceUrl case above — no link, and no
      // fallback button either.
      expect(screen.queryByRole("link", { name: "Apply" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
      expect(matchingClient.getApplyRedirectUrl).not.toHaveBeenCalled();
    });

    it("distinguishes the manual-entry link from the real-posting Apply button's redirect href", () => {
      // Sanity check that the two code paths are genuinely different, not just two
      // assertions that happen to both pass: the real-posting row's href must be the
      // apply-redirect BFF route, while the manual row's href must be its own sourceUrl.
      const { unmount } = render(<TrackedMatchRow match={baseMatch} />, { wrapper });
      expect(screen.getByRole("link", { name: "Apply" })).toHaveAttribute(
        "href",
        "/api/matches/m1/apply-redirect",
      );
      unmount();

      render(<TrackedMatchRow match={manualMatch} />, { wrapper });
      expect(screen.getByRole("link", { name: "Apply" })).toHaveAttribute(
        "href",
        manualMatch.sourceUrl,
      );
    });
  });

  it("renders no interview chip when nextInterviewAt is null", () => {
    render(<TrackedMatchRow match={baseMatch} />, { wrapper });
    expect(screen.queryByText(/Interview:/)).not.toBeInTheDocument();
  });

  it('renders InterviewScheduleCard inline when applicationStatus is "interview"', () => {
    render(<TrackedMatchRow match={{ ...baseMatch, applicationStatus: "interview" }} />, {
      wrapper,
    });
    // Stubbed useInterviewSchedule resolves to null, so the card renders its
    // "Schedule interview" CTA rather than the full card (§15.5).
    expect(screen.getByRole("button", { name: "Schedule interview" })).toBeInTheDocument();
  });

  it("does not render InterviewScheduleCard for non-interview statuses", () => {
    render(<TrackedMatchRow match={baseMatch} />, { wrapper });
    expect(screen.queryByRole("button", { name: "Schedule interview" })).not.toBeInTheDocument();
  });
});
