import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { usePreferences, useUpdatePreferences } from "./usePreferences";
import * as client from "../api/client";
import type { CandidateJobPreferences } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const samplePreferences: CandidateJobPreferences = {
  userId: "u1",
  sourceDocumentId: null,
  desiredRoles: ["Engineer"],
  desiredLocations: [],
  remotePreference: "remote",
  salaryMin: null,
  salaryMax: null,
  salaryCurrency: "USD",
  notificationChannels: ["email"],
  digestFrequency: "daily",
  isScanEnabled: true,
  lastScannedAt: null,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("usePreferences", () => {
  it("returns preferences data on success", async () => {
    vi.spyOn(client, "fetchPreferences").mockResolvedValue(samplePreferences);

    const { result } = renderHook(() => usePreferences(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.desiredRoles).toEqual(["Engineer"]);
  });

  it("does not retry on 404", async () => {
    vi.spyOn(client, "fetchPreferences").mockRejectedValue(
      new Error("Failed to fetch preferences: 404"),
    );
    const { result } = renderHook(() => usePreferences(), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("useUpdatePreferences", () => {
  it("mutates and stores the returned preferences in the cache", async () => {
    vi.spyOn(client, "updatePreferences").mockResolvedValue({
      ...samplePreferences,
      isScanEnabled: false,
    });

    const { result } = renderHook(() => useUpdatePreferences(), { wrapper });
    result.current.mutate({ isScanEnabled: false });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.updatePreferences).toHaveBeenCalledWith({ isScanEnabled: false });
  });
});
