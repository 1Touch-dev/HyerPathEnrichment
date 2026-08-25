import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  useOutreachMessages,
  useDraftOutreach,
  useEditOutreachDraft,
  useSendOutreach,
  useCompanyTier,
  useSetCompanyTier,
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
  messageType: "email",
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

  it("threads strategy/referralContext/roleType/seniority through to draftOutreach", async () => {
    vi.spyOn(apiClient, "draftOutreach").mockResolvedValue({
      success: true,
      data: { rqJobId: "rq2", message: "Outreach draft generation started" },
    });

    const { result } = renderHook(() => useDraftOutreach(), { wrapper });
    result.current.mutate({
      companyName: "Acme",
      documentId: "doc1",
      strategy: "warm_referral",
      referralContext: "Referred by Jane Doe.",
      roleType: "technical",
      seniority: "senior",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiClient.draftOutreach).toHaveBeenCalledWith({
      companyName: "Acme",
      documentId: "doc1",
      strategy: "warm_referral",
      referralContext: "Referred by Jane Doe.",
      roleType: "technical",
      seniority: "senior",
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

describe("useCompanyTier", () => {
  it("calls getCompanyTier with the given companyName and returns the unwrapped result", async () => {
    vi.spyOn(apiClient, "getCompanyTier").mockResolvedValue({
      success: true,
      data: {
        companyName: "Acme",
        tier: "premium",
        notes: null,
        updatedAt: "2026-01-01T00:00:00Z",
      },
    });

    const { result } = renderHook(() => useCompanyTier("Acme"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiClient.getCompanyTier).toHaveBeenCalledWith("Acme");
    expect(result.current.data?.tier).toBe("premium");
  });

  it("does not call getCompanyTier when companyName is empty", () => {
    vi.spyOn(apiClient, "getCompanyTier").mockResolvedValue({ success: true, data: null });

    renderHook(() => useCompanyTier(""), { wrapper });

    expect(apiClient.getCompanyTier).not.toHaveBeenCalled();
  });
});

describe("useSetCompanyTier", () => {
  it("calls setCompanyTier with the correct arguments on success", async () => {
    vi.spyOn(apiClient, "setCompanyTier").mockResolvedValue({
      success: true,
      data: {
        companyName: "Acme",
        tier: "outsourcing",
        notes: null,
        updatedAt: "2026-01-01T00:00:00Z",
      },
    });

    const { result } = renderHook(() => useSetCompanyTier(), { wrapper });
    result.current.mutate({ companyName: "Acme", tier: "outsourcing" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiClient.setCompanyTier).toHaveBeenCalledWith("Acme", "outsourcing", undefined);
  });
});
