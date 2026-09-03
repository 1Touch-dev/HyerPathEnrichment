import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { JobPostingsModerationPanel } from "./JobPostingsModerationPanel";
import * as useJobPostingsModerationHooks from "../hooks/useJobPostingsModeration";
import type { AdminJobPosting, AdminJobPostingListResponse } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/desk/job-postings",
}));

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const basePosting: AdminJobPosting = {
  id: "p1",
  title: "Senior Backend Engineer",
  company: "Acme Corp",
  location: "Remote",
  remote: true,
  source: "linkedin",
  sourceUrl: "https://example.com/job/p1",
  salaryMin: 120000,
  salaryMax: 160000,
  salaryCurrency: "USD",
  postedAt: "2026-01-01T00:00:00Z",
  firstSeenAt: "2026-01-01T00:00:00Z",
  lastSeenAt: "2026-01-02T00:00:00Z",
  isActive: true,
  moderationStatus: "active",
  moderatedBy: null,
  moderatedAt: null,
};

const sampleList: AdminJobPostingListResponse = {
  items: [basePosting],
  nextCursor: null,
  hasMore: false,
};

function mockUseAdminJobPostings(
  overrides: Partial<UseQueryResult<AdminJobPostingListResponse>> = {},
) {
  vi.spyOn(useJobPostingsModerationHooks, "useAdminJobPostings").mockReturnValue({
    data: sampleList,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<AdminJobPostingListResponse>);
}

const moderateMutate = vi.fn();
const moderateMutateAsync = vi.fn();

function mockUseModerateJobPosting(
  overrides: Partial<ReturnType<typeof useJobPostingsModerationHooks.useModerateJobPosting>> = {},
) {
  vi.spyOn(useJobPostingsModerationHooks, "useModerateJobPosting").mockReturnValue({
    mutate: moderateMutate,
    mutateAsync: moderateMutateAsync,
    isPending: false,
    ...overrides,
  } as unknown as ReturnType<typeof useJobPostingsModerationHooks.useModerateJobPosting>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  moderateMutate.mockReset();
  moderateMutateAsync.mockReset().mockResolvedValue(undefined);
  mockUseAdminJobPostings();
  mockUseModerateJobPosting();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("JobPostingsModerationPanel", () => {
  it("renders a row per job posting with title, company, and status badge", () => {
    render(<JobPostingsModerationPanel />, { wrapper });
    expect(screen.getByText("Senior Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("renders an empty state when there are no job postings", () => {
    mockUseAdminJobPostings({ data: { items: [], nextCursor: null, hasMore: false } });
    render(<JobPostingsModerationPanel />, { wrapper });
    expect(screen.getByText("No job postings found")).toBeInTheDocument();
  });

  it("opens the moderate dialog and calls useModerateJobPosting when Hide is confirmed", async () => {
    render(<JobPostingsModerationPanel />, { wrapper });
    fireEvent.click(screen.getByText("Hide"));

    expect(screen.getByText('Hide "Senior Backend Engineer"?')).toBeInTheDocument();

    const reasonInput = screen.getByLabelText("Reason (optional)");
    fireEvent.change(reasonInput, { target: { value: "Reported as spam" } });

    const form = reasonInput.closest("form");
    expect(form).not.toBeNull();
    form!.requestSubmit();

    await waitFor(() =>
      expect(moderateMutateAsync).toHaveBeenCalledWith({
        id: "p1",
        moderationStatus: "hidden",
        reason: "Reported as spam",
      }),
    );
  });

  it("calls useModerateJobPosting with the removed status when Remove is confirmed", async () => {
    render(<JobPostingsModerationPanel />, { wrapper });
    fireEvent.click(screen.getByText("Remove"));

    const form = screen.getByLabelText("Reason (optional)").closest("form");
    expect(form).not.toBeNull();
    form!.requestSubmit();

    await waitFor(() =>
      expect(moderateMutateAsync).toHaveBeenCalledWith({
        id: "p1",
        moderationStatus: "removed",
        reason: undefined,
      }),
    );
  });

  it("shows a Restore action for hidden postings, and calls moderate to active after confirmation", () => {
    mockUseAdminJobPostings({
      data: {
        items: [{ ...basePosting, moderationStatus: "hidden" }],
        nextCursor: null,
        hasMore: false,
      },
    });
    render(<JobPostingsModerationPanel />, { wrapper });
    fireEvent.click(screen.getByText("Restore"));
    expect(moderateMutate).toHaveBeenCalledWith({ id: "p1", moderationStatus: "active" });
  });

  it("does not call moderate when the Restore confirmation is declined", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    mockUseAdminJobPostings({
      data: {
        items: [{ ...basePosting, moderationStatus: "hidden" }],
        nextCursor: null,
        hasMore: false,
      },
    });
    render(<JobPostingsModerationPanel />, { wrapper });
    fireEvent.click(screen.getByText("Restore"));
    expect(moderateMutate).not.toHaveBeenCalled();
  });

  it("disables the Next page button when hasMore is false", () => {
    render(<JobPostingsModerationPanel />, { wrapper });
    expect(screen.getByText("Next page")).toBeDisabled();
  });

  it("enables the Next page button when hasMore is true", () => {
    mockUseAdminJobPostings({
      data: { items: [basePosting], nextCursor: "cursor2", hasMore: true },
    });
    render(<JobPostingsModerationPanel />, { wrapper });
    expect(screen.getByText("Next page")).not.toBeDisabled();
  });
});
