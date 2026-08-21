import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AnalyticsPanel } from "./AnalyticsPanel";
import * as useAnalyticsHooks from "../hooks/useAnalytics";
import type { JobMatchAnalytics } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleAnalytics: JobMatchAnalytics = {
  totalPostings: 1000,
  totalMatches: 250,
  postingsBySource: { linkedin: 600, indeed: 400 },
  topCompanies: [
    { company: "Acme", count: 50 },
    { company: "Globex", count: 30 },
  ],
  avgSalaryMin: 90000,
  avgSalaryMax: 130000,
  avgOverallScore: 78.4,
  computedAt: "2026-01-01T00:00:00Z",
  cacheHit: true,
};

const refreshMock = vi.fn();

function mockUseJobMatchAnalytics(
  overrides: Partial<ReturnType<typeof useAnalyticsHooks.useJobMatchAnalytics>> = {},
) {
  vi.spyOn(useAnalyticsHooks, "useJobMatchAnalytics").mockReturnValue({
    data: sampleAnalytics,
    isLoading: false,
    isRefetching: false,
    refresh: refreshMock,
    ...overrides,
  } as ReturnType<typeof useAnalyticsHooks.useJobMatchAnalytics>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  refreshMock.mockReset().mockResolvedValue(undefined);
  mockUseJobMatchAnalytics();
});

describe("AnalyticsPanel", () => {
  it("renders a loading message while analytics are loading", () => {
    mockUseJobMatchAnalytics({ data: undefined, isLoading: true });
    render(<AnalyticsPanel />, { wrapper });
    expect(screen.getByText("Loading analytics…")).toBeInTheDocument();
  });

  it("labels the panel as aggregate stats, not a full analytics suite", () => {
    render(<AnalyticsPanel />, { wrapper });
    expect(screen.getByText("Aggregate stats, not a full analytics suite.")).toBeInTheDocument();
  });

  it("renders total postings, total matches, avg salary range, and avg match score", () => {
    render(<AnalyticsPanel />, { wrapper });
    expect(screen.getByText("1,000")).toBeInTheDocument();
    expect(screen.getByText("250")).toBeInTheDocument();
    expect(screen.getByText("$90,000 – $130,000")).toBeInTheDocument();
    expect(screen.getByText("78")).toBeInTheDocument();
  });

  it("renders postings by source and top 10 companies", () => {
    render(<AnalyticsPanel />, { wrapper });
    expect(screen.getByText("linkedin")).toBeInTheDocument();
    expect(screen.getByText("indeed")).toBeInTheDocument();
    expect(screen.getByText("1. Acme")).toBeInTheDocument();
    expect(screen.getByText("2. Globex")).toBeInTheDocument();
  });

  it("shows a cache hit indicator when cacheHit is true", () => {
    render(<AnalyticsPanel />, { wrapper });
    expect(screen.getByText("Cache hit")).toBeInTheDocument();
  });

  it("shows a freshly-computed indicator when cacheHit is false", () => {
    mockUseJobMatchAnalytics({ data: { ...sampleAnalytics, cacheHit: false } });
    render(<AnalyticsPanel />, { wrapper });
    expect(screen.getByText("Freshly computed")).toBeInTheDocument();
  });

  it("calls refresh (bypassing the cache) when the Refresh button is clicked", async () => {
    render(<AnalyticsPanel />, { wrapper });
    fireEvent.click(screen.getByText("Refresh"));
    await waitFor(() => expect(refreshMock).toHaveBeenCalledTimes(1));
  });
});
