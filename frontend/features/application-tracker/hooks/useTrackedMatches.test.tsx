import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTrackedMatches } from "./useTrackedMatches";
import * as client from "../api/client";
import type { TrackedMatchListResponse } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleList: TrackedMatchListResponse = {
  matches: [
    {
      matchId: "m1",
      jobPostingId: "jp1",
      title: "Senior Engineer",
      company: "Acme",
      location: "Remote",
      remote: true,
      sourceUrl: null,
      overallScore: 88,
      applicationStatus: "new",
      applyClickedAt: null,
      appliedAt: null,
      statusUpdatedAt: null,
      createdAt: "2026-01-01T00:00:00Z",
      nextInterviewAt: null,
    },
  ],
  total: 1,
  limit: 20,
  offset: 0,
  countsByStatus: {
    new: 1,
    applied: 0,
    replied: 0,
    interview: 0,
    offer: 0,
    rejected: 0,
  },
};

describe("useTrackedMatches", () => {
  it("returns tracked matches data on success", async () => {
    vi.spyOn(client, "fetchTrackedMatches").mockResolvedValue(sampleList);

    const { result } = renderHook(() => useTrackedMatches(undefined, "newest", 20, 0), {
      wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.matches).toHaveLength(1);
    expect(client.fetchTrackedMatches).toHaveBeenCalledWith(undefined, "newest", 20, 0);
  });

  it("passes the status filter through to the client", async () => {
    vi.spyOn(client, "fetchTrackedMatches").mockResolvedValue(sampleList);

    const { result } = renderHook(() => useTrackedMatches("interview", "score", 20, 0), {
      wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.fetchTrackedMatches).toHaveBeenCalledWith("interview", "score", 20, 0);
  });
});
