import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useSubmitSwipe, useSwipeDeck } from "./useSwipeDeck";
import * as apiClient from "@/src/lib/api-client";
import { jobSwipeKeys } from "../api/keys";
import type { SwipeDeck } from "@/src/lib/types";

function makeWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const sampleDeck: SwipeDeck = {
  cards: [
    {
      matchId: "m1",
      jobPostingId: "jp1",
      title: "Senior Engineer",
      company: "Acme",
      location: "Remote",
      remote: true,
      salaryMin: null,
      salaryMax: null,
      salaryCurrency: null,
      overallScore: 88,
      explanation: null,
      belowSimilarityThreshold: false,
    },
    {
      matchId: "m2",
      jobPostingId: "jp2",
      title: "Staff Engineer",
      company: "Globex",
      location: "NYC",
      remote: false,
      salaryMin: null,
      salaryMax: null,
      salaryCurrency: null,
      overallScore: 75,
      explanation: null,
      belowSimilarityThreshold: false,
    },
  ],
  hasMore: false,
};

describe("useSwipeDeck", () => {
  it("returns deck data on success", async () => {
    vi.spyOn(apiClient, "fetchSwipeDeck").mockResolvedValue({
      success: true,
      data: sampleDeck,
      message: null,
      meta: null,
    });

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useSwipeDeck(), { wrapper: makeWrapper(queryClient) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.cards).toHaveLength(2);
  });
});

describe("useSubmitSwipe", () => {
  it("optimistically removes the matching card from cached deck data via onMutate", async () => {
    vi.spyOn(apiClient, "submitSwipe").mockResolvedValue({
      success: true,
      data: { direction: "right" },
      message: null,
      meta: null,
    });

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(jobSwipeKeys.deck(), sampleDeck);

    const { result } = renderHook(() => useSubmitSwipe(), { wrapper: makeWrapper(queryClient) });
    result.current.mutate({ matchId: "m1", direction: "right" });

    await waitFor(() => {
      const cached = queryClient.getQueryData<{ cards: { matchId: string }[] }>(
        jobSwipeKeys.deck(),
      );
      expect(cached?.cards.some((c) => c.matchId === "m1")).toBe(false);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it("does not restore the removed card when the mutation is rejected", async () => {
    vi.spyOn(apiClient, "submitSwipe").mockRejectedValue(new Error("network error"));
    vi.spyOn(console, "error").mockImplementation(() => {});

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(jobSwipeKeys.deck(), sampleDeck);

    const { result } = renderHook(() => useSubmitSwipe(), { wrapper: makeWrapper(queryClient) });
    result.current.mutate({ matchId: "m1", direction: "right" });

    await waitFor(() => expect(result.current.isError).toBe(true));

    const cached = queryClient.getQueryData<{ cards: { matchId: string }[] }>(jobSwipeKeys.deck());
    expect(cached?.cards.some((c) => c.matchId === "m1")).toBe(false);
  });
});
