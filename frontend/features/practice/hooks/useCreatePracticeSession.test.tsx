import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useCreatePracticeSession } from "./useCreatePracticeSession";
import * as apiClient from "@/src/lib/api-client";
import type { PracticeSession } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleSession: PracticeSession = {
  id: "session-1",
  sessionType: "mock_interview",
  status: "pending",
  questionsAttempted: 0,
  questionsCompleted: 0,
  overallScore: null,
  startedAt: "2026-01-01T00:00:00Z",
  completedAt: null,
  attempts: [],
};

describe("useCreatePracticeSession", () => {
  it("calls createPracticeSession with the session type and optional metadata", async () => {
    vi.spyOn(apiClient, "createPracticeSession").mockResolvedValue({
      success: true,
      data: sampleSession,
    });

    const { result } = renderHook(() => useCreatePracticeSession(), { wrapper });
    result.current.mutate({ sessionType: "mock_interview" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiClient.createPracticeSession).toHaveBeenCalledWith("mock_interview", undefined);
    expect(result.current.data).toEqual(sampleSession);
  });

  it("forwards metadata when provided", async () => {
    vi.spyOn(apiClient, "createPracticeSession").mockResolvedValue({
      success: true,
      data: sampleSession,
    });

    const { result } = renderHook(() => useCreatePracticeSession(), { wrapper });
    result.current.mutate({ sessionType: "mock_interview", metadata: { source: "landing" } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiClient.createPracticeSession).toHaveBeenCalledWith("mock_interview", {
      source: "landing",
    });
  });
});
