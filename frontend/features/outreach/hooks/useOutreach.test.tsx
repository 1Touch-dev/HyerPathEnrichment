import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  useOutreachMessages,
  useDraftOutreach,
  useEditOutreachDraft,
  useSendOutreach,
} from "./useOutreach";
import * as apiClient from "@/src/lib/api-client";
import type { OutreachListResponse, OutreachMessage } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleMessage: OutreachMessage = {
  messageId: "msg1",
  companyName: "Acme",
  recipientRoleTitle: "Hiring Manager",
  subject: "Excited about the role",
  body: "Hello there",
  status: "draft",
  createdAt: "2026-01-01T00:00:00Z",
  sentAt: null,
};

const sampleList: OutreachListResponse = { messages: [sampleMessage] };

describe("useOutreachMessages", () => {
  it("returns the unwrapped messages list on success", async () => {
    vi.spyOn(apiClient, "fetchOutreachMessages").mockResolvedValue({
      success: true,
      data: sampleList,
    });

    const { result } = renderHook(() => useOutreachMessages(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.messages).toHaveLength(1);
    expect(apiClient.fetchOutreachMessages).toHaveBeenCalled();
  });
});

describe("useDraftOutreach", () => {
  it("calls draftOutreach with the correct arguments and invalidates the list on success", async () => {
    vi.spyOn(apiClient, "draftOutreach").mockResolvedValue({
      success: true,
      data: { rqJobId: "rq1", message: "Outreach draft generation started" },
    });

    const { result } = renderHook(() => useDraftOutreach(), { wrapper });
    result.current.mutate({ companyName: "Acme", documentId: "doc1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiClient.draftOutreach).toHaveBeenCalledWith({
      companyName: "Acme",
      documentId: "doc1",
    });
  });
});

describe("useEditOutreachDraft", () => {
  it("calls editOutreachDraft with the correct arguments and invalidates the list on success", async () => {
    vi.spyOn(apiClient, "editOutreachDraft").mockResolvedValue({
      success: true,
      data: sampleMessage,
    });

    const { result } = renderHook(() => useEditOutreachDraft(), { wrapper });
    result.current.mutate({ messageId: "msg1", subject: "New subject", body: "New body" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiClient.editOutreachDraft).toHaveBeenCalledWith("msg1", "New subject", "New body");
  });
});

describe("useSendOutreach", () => {
  it("calls sendOutreach with the correct message id and invalidates the list on success", async () => {
    vi.spyOn(apiClient, "sendOutreach").mockResolvedValue({
      success: true,
      data: { ...sampleMessage, status: "sent" },
    });

    const { result } = renderHook(() => useSendOutreach(), { wrapper });
    result.current.mutate("msg1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiClient.sendOutreach).toHaveBeenCalledWith("msg1");
  });
});
