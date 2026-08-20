import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ReviewQueueTable } from "./ReviewQueueTable";
import * as useReviewQueueHooks from "../hooks/useReviewQueue";
import type {
  AdminReviewQueueDetail,
  AdminReviewQueueItem,
  AdminReviewQueueListResponse,
} from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const baseItem: AdminReviewQueueItem = {
  id: "rq1",
  resourceType: "job_posting",
  resourceId: "res1",
  status: "pending",
  flagReason: "duplicate content",
  flagSource: "heuristic",
  flaggedAt: "2026-01-01T00:00:00Z",
  reviewedBy: null,
  reviewedAt: null,
  reviewNotes: null,
};

const sampleList: AdminReviewQueueListResponse = {
  items: [baseItem],
  nextCursor: null,
  hasMore: false,
};

const sampleDetail: AdminReviewQueueDetail = {
  item: baseItem,
  resolvedResource: { id: "res1", title: "Software Engineer" },
};

function mockUseReviewQueue(overrides: Partial<UseQueryResult<AdminReviewQueueListResponse>> = {}) {
  vi.spyOn(useReviewQueueHooks, "useReviewQueue").mockReturnValue({
    data: sampleList,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<AdminReviewQueueListResponse>);
}

function mockUseReviewQueueItem(overrides: Partial<UseQueryResult<AdminReviewQueueDetail>> = {}) {
  vi.spyOn(useReviewQueueHooks, "useReviewQueueItem").mockReturnValue({
    data: sampleDetail,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<AdminReviewQueueDetail>);
}

const decideMutate = vi.fn();

function mockDecideMutation() {
  vi.spyOn(useReviewQueueHooks, "useDecideReviewQueueItem").mockReturnValue({
    mutate: decideMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useReviewQueueHooks.useDecideReviewQueueItem>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  decideMutate.mockReset();
  mockUseReviewQueue();
  mockUseReviewQueueItem();
  mockDecideMutation();
});

describe("ReviewQueueTable", () => {
  it("renders a row per item with resource type, flag reason/source, and status", () => {
    render(<ReviewQueueTable />, { wrapper });
    expect(screen.getByText("job_posting")).toBeInTheDocument();
    expect(screen.getByText("duplicate content")).toBeInTheDocument();
    expect(screen.getByText("heuristic")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
  });

  it("renders an empty state when there are no items", () => {
    mockUseReviewQueue({ data: { items: [], nextCursor: null, hasMore: false } });
    render(<ReviewQueueTable />, { wrapper });
    expect(screen.getByText("No review queue items found")).toBeInTheDocument();
  });

  it("disables the Next page button when hasMore is false", () => {
    render(<ReviewQueueTable />, { wrapper });
    expect(screen.getByText("Next page")).toBeDisabled();
  });

  it("enables the Next page button when hasMore is true", () => {
    mockUseReviewQueue({ data: { items: [baseItem], nextCursor: "cursor2", hasMore: true } });
    render(<ReviewQueueTable />, { wrapper });
    expect(screen.getByText("Next page")).not.toBeDisabled();
  });

  it("opens the detail drawer when Review is clicked", () => {
    render(<ReviewQueueTable />, { wrapper });
    fireEvent.click(screen.getByText("Review"));
    expect(screen.getByText("Review queue item")).toBeInTheDocument();
  });
});
