import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  useAddPortfolioItem,
  useDeletePortfolioItem,
  usePortfolioProfile,
} from "./usePortfolioProfile";
import { portfolioKeys } from "../api/keys";
import * as apiClient from "@/src/lib/api-client";
import type { SuccessEnvelope } from "@/src/lib/api-envelope";
import type { PortfolioProfile } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleProfile: PortfolioProfile = {
  profileId: "p1",
  userId: "u1",
  slug: "jane-doe",
  displayName: "Jane Doe",
  headline: "Backend Engineer",
  summary: "I build things.",
  isPublished: true,
  publicUrl: "/p/jane-doe",
  items: [],
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

function envelope<T>(data: T): SuccessEnvelope<T> {
  return { success: true, data, message: null, meta: null };
}

describe("usePortfolioProfile", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("returns profile data on success", async () => {
    vi.spyOn(apiClient, "fetchPortfolioProfile").mockResolvedValue(envelope(sampleProfile));

    const { result } = renderHook(() => usePortfolioProfile(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.slug).toBe("jane-doe");
  });

  it("does not retry on a 404", async () => {
    vi.spyOn(apiClient, "fetchPortfolioProfile").mockRejectedValue(
      new Error("Failed to fetch portfolio profile: 404"),
    );

    const { result } = renderHook(() => usePortfolioProfile(), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(apiClient.fetchPortfolioProfile).toHaveBeenCalledTimes(1);
  });
});

describe("useAddPortfolioItem", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("invalidates the profile query on success", async () => {
    vi.spyOn(apiClient, "addPortfolioItem").mockResolvedValue(
      envelope({
        itemId: "i1",
        itemType: "other_link" as const,
        title: "My project",
        description: null,
        url: "https://example.com",
        displayOrder: 0,
      }),
    );

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    function localWrapper({ children }: { children: ReactNode }) {
      return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    }

    const { result } = renderHook(() => useAddPortfolioItem(), { wrapper: localWrapper });
    result.current.mutate({
      itemType: "other_link",
      title: "My project",
      description: null,
      url: "https://example.com",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: portfolioKeys.profile() });
  });
});

describe("useDeletePortfolioItem", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("invalidates the profile query on success", async () => {
    vi.spyOn(apiClient, "deletePortfolioItem").mockResolvedValue(envelope({ deleted: true }));

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    function localWrapper({ children }: { children: ReactNode }) {
      return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    }

    const { result } = renderHook(() => useDeletePortfolioItem(), { wrapper: localWrapper });
    result.current.mutate("i1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: portfolioKeys.profile() });
  });
});
