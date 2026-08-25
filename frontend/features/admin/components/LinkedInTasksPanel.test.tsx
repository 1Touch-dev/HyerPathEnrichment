import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { LinkedInTasksPanel } from "./LinkedInTasksPanel";
import * as hooks from "../hooks/useLinkedInSendTasks";
import type { LinkedInSendTask } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const baseTask: LinkedInSendTask = {
  id: "t1",
  outreachMessageId: "m1",
  batchId: null,
  linkedinProfileUrl: "https://www.linkedin.com/in/jane-recruiter",
  actionType: "direct_message",
  status: "pending",
  claimedBy: null,
  claimedAt: null,
  completedAt: null,
  outcomeNote: null,
  createdAt: "2026-01-01T00:00:00Z",
};

function mockUseLinkedInTasks(overrides: Partial<UseQueryResult<LinkedInSendTask[]>> = {}) {
  vi.spyOn(hooks, "useLinkedInTasks").mockReturnValue({
    data: [baseTask],
    isLoading: false,
    ...overrides,
  } as UseQueryResult<LinkedInSendTask[]>);
}

const claimMutate = vi.fn();
const completeMutate = vi.fn();
const skipMutate = vi.fn();
const createBatchMutateAsync = vi.fn();
const startBatchMutate = vi.fn();

function mockMutations() {
  vi.spyOn(hooks, "useClaimLinkedInTask").mockReturnValue({
    mutate: claimMutate,
    isPending: false,
  } as unknown as ReturnType<typeof hooks.useClaimLinkedInTask>);
  vi.spyOn(hooks, "useCompleteLinkedInTask").mockReturnValue({
    mutate: completeMutate,
    isPending: false,
  } as unknown as ReturnType<typeof hooks.useCompleteLinkedInTask>);
  vi.spyOn(hooks, "useSkipLinkedInTask").mockReturnValue({
    mutate: skipMutate,
    isPending: false,
  } as unknown as ReturnType<typeof hooks.useSkipLinkedInTask>);
  vi.spyOn(hooks, "useCreateLinkedInSendBatch").mockReturnValue({
    mutateAsync: createBatchMutateAsync,
    isPending: false,
  } as unknown as ReturnType<typeof hooks.useCreateLinkedInSendBatch>);
  vi.spyOn(hooks, "useStartLinkedInSendBatch").mockReturnValue({
    mutate: startBatchMutate,
    isPending: false,
  } as unknown as ReturnType<typeof hooks.useStartLinkedInSendBatch>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  claimMutate.mockReset();
  completeMutate.mockReset();
  skipMutate.mockReset();
  createBatchMutateAsync.mockReset();
  startBatchMutate.mockReset();
  mockUseLinkedInTasks();
  mockMutations();
  vi.spyOn(window, "prompt").mockReturnValue("");
});

describe("LinkedInTasksPanel", () => {
  it("renders a row per task with profile URL, action, and status", () => {
    render(<LinkedInTasksPanel />, { wrapper });
    expect(screen.getByText("https://www.linkedin.com/in/jane-recruiter")).toBeInTheDocument();
    expect(screen.getByText("direct message")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
  });

  it("renders an empty state when there are no tasks", () => {
    mockUseLinkedInTasks({ data: [] });
    render(<LinkedInTasksPanel />, { wrapper });
    expect(screen.getByText("No LinkedIn tasks found")).toBeInTheDocument();
  });

  it("calls useClaimLinkedInTask when Claim is clicked", () => {
    render(<LinkedInTasksPanel />, { wrapper });
    fireEvent.click(screen.getByText("Claim"));
    expect(claimMutate).toHaveBeenCalledWith("t1");
  });

  it("calls useCompleteLinkedInTask with the operator's outcome note when Mark sent is clicked", () => {
    vi.spyOn(window, "prompt").mockReturnValue("sent via LinkedIn");
    render(<LinkedInTasksPanel />, { wrapper });
    fireEvent.click(screen.getByText("Mark sent"));
    expect(completeMutate).toHaveBeenCalledWith({ taskId: "t1", outcomeNote: "sent via LinkedIn" });
  });

  it("does not call complete when the prompt is cancelled", () => {
    vi.spyOn(window, "prompt").mockReturnValue(null);
    render(<LinkedInTasksPanel />, { wrapper });
    fireEvent.click(screen.getByText("Mark sent"));
    expect(completeMutate).not.toHaveBeenCalled();
  });

  it("calls useSkipLinkedInTask when Skip is clicked", () => {
    render(<LinkedInTasksPanel />, { wrapper });
    fireEvent.click(screen.getByText("Skip"));
    expect(skipMutate).toHaveBeenCalled();
  });

  it("disables the create-batch button when no tasks are selected", () => {
    render(<LinkedInTasksPanel />, { wrapper });
    expect(screen.getByText("Create batch from selected (0)")).toBeDisabled();
  });
});
