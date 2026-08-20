import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { PortfolioModerationPanel } from "./PortfolioModerationPanel";
import * as usePortfolioModerationHooks from "../hooks/usePortfolioModeration";
import type { AdminPortfolioProfile, AdminPortfolioProfileListResponse } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const baseProfile: AdminPortfolioProfile = {
  profileId: "p1",
  userId: "u1",
  slug: "jane-doe",
  displayName: "Jane Doe",
  headline: "Software Engineer",
  bio: "Building things.",
  isPublished: true,
  adminHidden: false,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

const sampleList: AdminPortfolioProfileListResponse = {
  items: [baseProfile],
  nextCursor: null,
  hasMore: false,
};

function mockUseAdminPortfolioProfiles(
  overrides: Partial<UseQueryResult<AdminPortfolioProfileListResponse>> = {},
) {
  vi.spyOn(usePortfolioModerationHooks, "useAdminPortfolioProfiles").mockReturnValue({
    data: sampleList,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<AdminPortfolioProfileListResponse>);
}

const moderateMutate = vi.fn();

function mockModerate(
  overrides: Partial<
    ReturnType<typeof usePortfolioModerationHooks.useModeratePortfolioProfile>
  > = {},
) {
  vi.spyOn(usePortfolioModerationHooks, "useModeratePortfolioProfile").mockReturnValue({
    mutate: moderateMutate,
    isPending: false,
    ...overrides,
  } as unknown as ReturnType<typeof usePortfolioModerationHooks.useModeratePortfolioProfile>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  moderateMutate.mockReset();
  mockUseAdminPortfolioProfiles();
  mockModerate();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("PortfolioModerationPanel", () => {
  it("renders a row per profile with slug, published, and moderation badges", () => {
    render(<PortfolioModerationPanel />, { wrapper });
    expect(screen.getByText("jane-doe")).toBeInTheDocument();
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    expect(screen.getAllByText("Published")).toHaveLength(2); // column header + badge
    expect(screen.getByText("Visible")).toBeInTheDocument();
  });

  it("renders an empty state when there are no profiles", () => {
    mockUseAdminPortfolioProfiles({ data: { items: [], nextCursor: null, hasMore: false } });
    render(<PortfolioModerationPanel />, { wrapper });
    expect(screen.getByText("No portfolio profiles found")).toBeInTheDocument();
  });

  it("calls useModeratePortfolioProfile when Hide is clicked, after confirmation", () => {
    render(<PortfolioModerationPanel />, { wrapper });
    fireEvent.click(screen.getByText("Hide"));
    expect(moderateMutate).toHaveBeenCalledWith({ profileId: "p1", adminHidden: true });
  });

  it("does not call useModeratePortfolioProfile when the confirmation is declined", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<PortfolioModerationPanel />, { wrapper });
    fireEvent.click(screen.getByText("Hide"));
    expect(moderateMutate).not.toHaveBeenCalled();
  });

  it("shows Unhide for already-hidden profiles and calls the mutation with adminHidden: false", () => {
    mockUseAdminPortfolioProfiles({
      data: { items: [{ ...baseProfile, adminHidden: true }], nextCursor: null, hasMore: false },
    });
    render(<PortfolioModerationPanel />, { wrapper });
    expect(screen.getByText("Hidden")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Unhide"));
    expect(moderateMutate).toHaveBeenCalledWith({ profileId: "p1", adminHidden: false });
  });

  it("disables the Next page button when hasMore is false", () => {
    render(<PortfolioModerationPanel />, { wrapper });
    expect(screen.getByText("Next page")).toBeDisabled();
  });

  it("enables the Next page button when hasMore is true", () => {
    mockUseAdminPortfolioProfiles({
      data: { items: [baseProfile], nextCursor: "cursor2", hasMore: true },
    });
    render(<PortfolioModerationPanel />, { wrapper });
    expect(screen.getByText("Next page")).not.toBeDisabled();
  });
});
