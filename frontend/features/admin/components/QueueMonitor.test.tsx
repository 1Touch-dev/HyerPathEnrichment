import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { QueueMonitor } from "./QueueMonitor";
import * as useQueuesHooks from "../hooks/useQueues";
import type { FailedJob, QueueSnapshot } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleQueues: QueueSnapshot[] = [
  {
    name: "default",
    priority: 1,
    queuedCount: 3,
    failedCount: 2,
    oldestQueuedAgeSeconds: 125,
    workersListening: 1,
  },
  {
    name: "notifications",
    priority: 2,
    queuedCount: 0,
    failedCount: 0,
    oldestQueuedAgeSeconds: null,
    workersListening: 2,
  },
];

const sampleFailedJobs: FailedJob[] = [
  {
    jobId: "job1",
    queueName: "default",
    funcName: "process_match",
    enqueuedAt: "2026-01-01T00:00:00Z",
    failedAt: "2026-01-01T00:05:00Z",
    excInfo: "ValueError: boom",
  },
];

function mockUseQueuesOverview(overrides: Partial<UseQueryResult<QueueSnapshot[]>> = {}) {
  vi.spyOn(useQueuesHooks, "useQueuesOverview").mockReturnValue({
    data: sampleQueues,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<QueueSnapshot[]>);
}

function mockUseFailedJobs(overrides: Partial<UseQueryResult<FailedJob[]>> = {}) {
  vi.spyOn(useQueuesHooks, "useFailedJobs").mockReturnValue({
    data: sampleFailedJobs,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<FailedJob[]>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  mockUseQueuesOverview();
  mockUseFailedJobs();
});

describe("QueueMonitor", () => {
  it("renders one row per queue with queued/failed count, age, and worker count", () => {
    render(<QueueMonitor />, { wrapper });
    expect(screen.getByText("default")).toBeInTheDocument();
    expect(screen.getByText("notifications")).toBeInTheDocument();
    expect(screen.getByText("2m")).toBeInTheDocument();
  });

  it("renders an empty state when there are no queues", () => {
    mockUseQueuesOverview({ data: [] });
    render(<QueueMonitor />, { wrapper });
    expect(screen.getByText("No queues configured")).toBeInTheDocument();
  });

  it("shows a dash for oldest job age when there is no queued job", () => {
    render(<QueueMonitor />, { wrapper });
    const rows = screen.getAllByRole("row");
    const notificationsRow = rows.find((row) => row.textContent?.includes("notifications"));
    expect(notificationsRow?.textContent).toContain("—");
  });

  it("expands the failed-job sub-table when clicking a queue's failed-count badge", async () => {
    render(<QueueMonitor />, { wrapper });
    const defaultRow = screen
      .getAllByRole("row")
      .find((row) => row.textContent?.includes("default"));
    expect(defaultRow).toBeDefined();
    fireEvent.click(within(defaultRow!).getByRole("button"));
    await waitFor(() => expect(screen.getByText("job1")).toBeInTheDocument());
    expect(screen.getByText("ValueError: boom")).toBeInTheDocument();
  });

  it("does not allow expanding a queue with zero failed jobs", () => {
    render(<QueueMonitor />, { wrapper });
    const notificationsRow = screen
      .getAllByRole("row")
      .find((row) => row.textContent?.includes("notifications"));
    expect(notificationsRow).toBeDefined();
    expect(within(notificationsRow!).getByRole("button")).toBeDisabled();
  });

  it("marks retry as unavailable for failed jobs", async () => {
    render(<QueueMonitor />, { wrapper });
    const defaultRow = screen
      .getAllByRole("row")
      .find((row) => row.textContent?.includes("default"));
    expect(defaultRow).toBeDefined();
    fireEvent.click(within(defaultRow!).getByRole("button"));
    await waitFor(() =>
      expect(screen.getByText("Retry unavailable in Wave 2")).toBeInTheDocument(),
    );
  });
});
