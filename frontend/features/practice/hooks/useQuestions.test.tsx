import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useQuestions } from "./useQuestions";
import * as apiClient from "@/src/lib/api-client";
import type { QuestionListResult } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleQuestions: QuestionListResult = {
  questions: [
    {
      id: "q1",
      questionText: "Tell me about a time you resolved a conflict.",
      category: "behavioral",
      difficulty: "medium",
      jobRoles: ["software_engineer"],
      technologies: [],
      isPersonalized: false,
    },
  ],
  source: "question_bank",
};

describe("useQuestions", () => {
  it("is a mutation (not a query) - does not fetch until explicitly triggered", () => {
    vi.spyOn(apiClient, "fetchQuestions").mockResolvedValue({
      success: true,
      data: sampleQuestions,
    });

    const { result } = renderHook(() => useQuestions(), { wrapper });
    expect(result.current.isIdle).toBe(true);
    expect(apiClient.fetchQuestions).not.toHaveBeenCalled();
  });

  it("calls fetchQuestions with the given payload and returns unwrapped data", async () => {
    vi.spyOn(apiClient, "fetchQuestions").mockResolvedValue({
      success: true,
      data: sampleQuestions,
    });

    const { result } = renderHook(() => useQuestions(), { wrapper });
    result.current.mutate({ jobRole: "software_engineer", personalize: true });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiClient.fetchQuestions).toHaveBeenCalledWith({
      jobRole: "software_engineer",
      personalize: true,
    });
    expect(result.current.data?.questions).toHaveLength(1);
    expect(result.current.data?.source).toBe("question_bank");
  });

  it("surfaces errors from the API client", async () => {
    vi.spyOn(apiClient, "fetchQuestions").mockRejectedValue(new Error("network error"));

    const { result } = renderHook(() => useQuestions(), { wrapper });
    result.current.mutate({ jobRole: "software_engineer" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(Error);
  });
});
