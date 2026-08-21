import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useUpdateApplicationStatus } from "./useUpdateApplicationStatus";
import * as client from "../api/client";
import type { TrackedMatch } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const updatedMatch: TrackedMatch = {
  matchId: "m1",
  jobPostingId: "jp1",
  title: "Senior Engineer",
  company: "Acme",
  location: "Remote",
  remote: true,
  sourceUrl: null,
  overallScore: 88,
  applicationStatus: "applied",
  applyClickedAt: null,
  appliedAt: null,
  statusUpdatedAt: "2026-01-02T00:00:00Z",
  createdAt: "2026-01-01T00:00:00Z",
  nextInterviewAt: null,
};

describe("useUpdateApplicationStatus", () => {
  it("calls the client with the match id and new status", async () => {
    vi.spyOn(client, "updateApplicationStatus").mockResolvedValue(updatedMatch);

    const { result } = renderHook(() => useUpdateApplicationStatus(), { wrapper });
    result.current.mutate({ matchId: "m1", status: "applied" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.updateApplicationStatus).toHaveBeenCalledWith("m1", "applied");
    expect(result.current.data).toEqual(updatedMatch);
  });
});
