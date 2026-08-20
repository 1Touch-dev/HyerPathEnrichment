import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ReviewQueueDetail } from "./ReviewQueueDetail";
import * as useReviewQueueHooks from "../hooks/useReviewQueue";
import type { AdminReviewQueueDetail, AdminReviewQueueItem } from "@/src/lib/types";
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

const sampleDetail: AdminReviewQueueDetail = {
  item: baseItem,
  resolvedResource: { id: "res1", title: "Software Engineer" },
};

function mockUseReviewQueueItem(overrides: Partial<UseQueryResult<AdminReviewQueueDetail>> = {}) {
  vi.spyOn(useReviewQueueHooks, "useReviewQueueItem").mockReturnValue({
    data: sampleDetail,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<AdminReviewQueueDetail>);
}

const decideMutate = vi.fn();

function mockDecideMutation(overrides: { isPending?: boolean } = {}) {
  vi.spyOn(useReviewQueueHooks, "useDecideReviewQueueItem").mockReturnValue({
    mutate: decideMutate,
    isPending: false,
    ...overrides,
  } as unknown as ReturnType<typeof useReviewQueueHooks.useDecideReviewQueueItem>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  decideMutate.mockReset();
  mockUseReviewQueueItem();
  mockDecideMutation();
});

describe("ReviewQueueDetail", () => {
  it("renders item fields and the resolved resource preview", () => {
    render(<ReviewQueueDetail itemId="rq1" open onOpenChange={vi.fn()} />, { wrapper });
    expect(screen.getByText("duplicate content")).toBeInTheDocument();
    expect(screen.getByText("heuristic")).toBeInTheDocument();
    expect(screen.getByText(/Software Engineer/)).toBeInTheDocument();
  });

  it("shows a fallback message when resolved_resource is null", () => {
    mockUseReviewQueueItem({ data: { item: baseItem, resolvedResource: null } });
    render(<ReviewQueueDetail itemId="rq1" open onOpenChange={vi.fn()} />, { wrapper });
    expect(screen.getByText(/No resource preview available/)).toBeInTheDocument();
  });

  it("submits an approve decision with notes", () => {
    render(<ReviewQueueDetail itemId="rq1" open onOpenChange={vi.fn()} />, { wrapper });
    fireEvent.change(screen.getByPlaceholderText("Review notes (optional)"), {
      target: { value: "looks fine" },
    });
    fireEvent.click(screen.getByText("Submit decision"));
    expect(decideMutate).toHaveBeenCalledWith(
      { id: "rq1", status: "approved", reviewNotes: "looks fine" },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("closes the drawer on successful decision", () => {
    const onOpenChange = vi.fn();
    decideMutate.mockImplementation((_vars, opts) => opts?.onSuccess?.());
    render(<ReviewQueueDetail itemId="rq1" open onOpenChange={onOpenChange} />, { wrapper });
    fireEvent.click(screen.getByText("Submit decision"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("disables the submit button while the mutation is pending", () => {
    mockDecideMutation({ isPending: true });
    render(<ReviewQueueDetail itemId="rq1" open onOpenChange={vi.fn()} />, { wrapper });
    expect(screen.getByText("Submit decision")).toBeDisabled();
  });

  it("shows a loading state while the item is loading", () => {
    mockUseReviewQueueItem({ data: undefined, isLoading: true });
    render(<ReviewQueueDetail itemId="rq1" open onOpenChange={vi.fn()} />, { wrapper });
    expect(screen.getAllByText("Loading…").length).toBeGreaterThan(0);
  });
});
