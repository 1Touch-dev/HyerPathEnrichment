import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { usePracticeSession } from "./usePracticeSession";
import * as apiClient from "@/src/lib/api-client";
import type { PracticeAttempt, PracticeSession } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function makeAttempt(overrides: Partial<PracticeAttempt> = {}): PracticeAttempt {
  return {
    id: "attempt-1",
    sessionId: "session-1",
    userId: "user-1",
    questionId: "q1",
    questionText: null,
    responseType: "text",
    textResponse: "My answer",
    audioRecordingId: null,
    aiScore: null,
    scoreBreakdown: null,
    aiFeedback: null,
    timeTakenSeconds: null,
    attemptedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeSession(attempts: PracticeAttempt[]): PracticeSession {
  return {
    id: "session-1",
    sessionType: "mock_interview",
    status: "in_progress",
    questionsAttempted: attempts.length,
    questionsCompleted: attempts.filter((a) => a.aiScore !== null).length,
    overallScore: null,
    startedAt: "2026-01-01T00:00:00Z",
    completedAt: null,
    attempts,
  };
}

describe("usePracticeSession", () => {
  it("does not fetch when sessionId is undefined", () => {
    vi.spyOn(apiClient, "getPracticeSession");
    renderHook(() => usePracticeSession(undefined), { wrapper });
    expect(apiClient.getPracticeSession).not.toHaveBeenCalled();
  });

  it("fetches and returns the session when sessionId is provided", async () => {
    const session = makeSession([makeAttempt({ aiScore: 8 })]);
    vi.spyOn(apiClient, "getPracticeSession").mockResolvedValue({ success: true, data: session });

    const { result } = renderHook(() => usePracticeSession("session-1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiClient.getPracticeSession).toHaveBeenCalledWith("session-1");
    expect(result.current.data?.attempts).toHaveLength(1);
  });

  it("polls again after 3s while an attempt is unscored, and stops once every attempt is scored", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const pending = makeSession([makeAttempt({ aiScore: null })]);
      const scored = makeSession([makeAttempt({ aiScore: 9 })]);
      const getSpy = vi
        .spyOn(apiClient, "getPracticeSession")
        .mockResolvedValueOnce({ success: true, data: pending })
        .mockResolvedValueOnce({ success: true, data: scored });

      renderHook(() => usePracticeSession("session-1"), { wrapper });
      await waitFor(() => expect(getSpy).toHaveBeenCalledTimes(1));

      // Still pending -> refetchInterval keeps polling every 3s.
      await vi.advanceTimersByTimeAsync(3000);
      await waitFor(() => expect(getSpy).toHaveBeenCalledTimes(2));

      // Now scored -> refetchInterval returns false, no further polling.
      await vi.advanceTimersByTimeAsync(10_000);
      expect(getSpy).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("stops polling once every attempt has a non-null aiScore", async () => {
    const session = makeSession([
      makeAttempt({ aiScore: 9 }),
      makeAttempt({ id: "attempt-2", aiScore: 7 }),
    ]);
    vi.spyOn(apiClient, "getPracticeSession").mockResolvedValue({ success: true, data: session });

    const { result } = renderHook(() => usePracticeSession("session-1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.attempts.every((a) => a.aiScore !== null)).toBe(true);
  });
});
