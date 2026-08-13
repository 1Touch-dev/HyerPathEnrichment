import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useCvChat } from "./useCvChat";
import * as apiClient from "@/src/lib/api-client";
import type { CvChatSession } from "@/src/lib/types";
import type { SuccessEnvelope } from "@/src/lib/api-envelope";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function envelope<T>(data: T): SuccessEnvelope<T> {
  return { success: true, data, message: null, meta: null };
}

const activeSession: CvChatSession = {
  sessionId: "s1",
  status: "active",
  missingFieldsAtStart: ["phone"],
  fieldsResolved: [],
  messages: [{ id: "m1", role: "assistant", content: "What is your phone number?", createdAt: "2026-01-01T00:00:00Z" }],
};

describe("useCvChat", () => {
  it("has no session before start.mutate() is called", () => {
    const { result } = renderHook(() => useCvChat("doc1"), { wrapper });
    expect(result.current.session).toBeNull();
  });

  it("populates session after start.mutate() succeeds", async () => {
    vi.spyOn(apiClient, "startCvChatSession").mockResolvedValue(envelope(activeSession));

    const { result } = renderHook(() => useCvChat("doc1"), { wrapper });
    result.current.start.mutate();

    await waitFor(() => expect(result.current.session?.sessionId).toBe("s1"));
    expect(apiClient.startCvChatSession).toHaveBeenCalledWith("doc1");
  });

  it("updates session from sendMessage response and invalidates completeness only when completed", async () => {
    vi.spyOn(apiClient, "startCvChatSession").mockResolvedValue(envelope(activeSession));
    const completedSession: CvChatSession = { ...activeSession, status: "completed" };
    vi.spyOn(apiClient, "postCvChatMessage").mockResolvedValue(envelope(completedSession));

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    function localWrapper({ children }: { children: ReactNode }) {
      return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    }

    const { result } = renderHook(() => useCvChat("doc1"), { wrapper: localWrapper });
    result.current.start.mutate();
    await waitFor(() => expect(result.current.session).not.toBeNull());

    result.current.sendMessage.mutate("555-1234");

    await waitFor(() => expect(result.current.session?.status).toBe("completed"));
    expect(apiClient.postCvChatMessage).toHaveBeenCalledWith("s1", "555-1234");
    expect(invalidateSpy).toHaveBeenCalled();
  });

  it("does not invalidate completeness when the turn does not complete the session", async () => {
    vi.spyOn(apiClient, "startCvChatSession").mockResolvedValue(envelope(activeSession));
    vi.spyOn(apiClient, "postCvChatMessage").mockResolvedValue(envelope(activeSession));

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    function localWrapper({ children }: { children: ReactNode }) {
      return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    }

    const { result } = renderHook(() => useCvChat("doc1"), { wrapper: localWrapper });
    result.current.start.mutate();
    await waitFor(() => expect(result.current.session).not.toBeNull());

    result.current.sendMessage.mutate("555-1234");
    await waitFor(() => expect(result.current.sendMessage.isSuccess).toBe(true));

    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});
