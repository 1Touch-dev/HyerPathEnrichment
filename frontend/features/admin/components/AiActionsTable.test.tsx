import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AiActionsTable } from "./AiActionsTable";
import * as useAiActionsHooks from "../hooks/useAiActions";
import type { AiAction, AiActionListResponse } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleAction: AiAction = {
  id: "action-1",
  actionType: "outreach_draft_generated",
  candidateUserId: "candidate-1",
  triggeredByUserId: "recruiter-1",
  relatedId: "draft-1",
  summary: "Generated an outreach draft",
  createdAt: "2026-01-01T00:00:00Z",
};

const sampleList: AiActionListResponse = {
  items: [sampleAction],
  nextCursor: null,
  hasMore: false,
};

function mockUseAiActions(overrides: Partial<UseQueryResult<AiActionListResponse>> = {}) {
  vi.spyOn(useAiActionsHooks, "useAiActions").mockReturnValue({
    data: sampleList,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<AiActionListResponse>);
}

function mockUseAiAction(overrides: Partial<UseQueryResult<AiAction>> = {}) {
  vi.spyOn(useAiActionsHooks, "useAiAction").mockReturnValue({
    data: sampleAction,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<AiAction>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  mockUseAiActions();
  mockUseAiAction();
});

describe("AiActionsTable", () => {
  it("renders a row per AI action", () => {
    render(<AiActionsTable />, { wrapper });
    expect(screen.getByText("outreach_draft_generated")).toBeInTheDocument();
    expect(screen.getByText("Generated an outreach draft")).toBeInTheDocument();
  });

  it("renders an empty state when there are no actions", () => {
    mockUseAiActions({ data: { items: [], nextCursor: null, hasMore: false } });
    render(<AiActionsTable />, { wrapper });
    expect(screen.getByText("No AI actions")).toBeInTheDocument();
  });

  it("disables Next page when hasMore is false", () => {
    render(<AiActionsTable />, { wrapper });
    expect(screen.getByText("Next page")).toBeDisabled();
  });

  it("opens the detail sheet with the full record when a row is clicked", () => {
    render(<AiActionsTable />, { wrapper });
    fireEvent.click(screen.getByText("outreach_draft_generated"));
    expect(screen.getByText("AI action")).toBeInTheDocument();
    expect(screen.getByText("draft-1")).toBeInTheDocument();
  });
});
