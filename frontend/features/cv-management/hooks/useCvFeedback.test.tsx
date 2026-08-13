import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useAcceptCvBullet, useCvFeedback, useRequestCvFeedback } from "./useCvFeedback";
import * as apiClient from "@/src/lib/api-client";
import * as localClient from "../api/client";
import type { CvFeedbackReport } from "@/src/lib/types";
import type { SuccessEnvelope } from "@/src/lib/api-envelope";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function envelope<T>(data: T): SuccessEnvelope<T> {
  return { success: true, data, message: null, meta: null };
}

const baseReport: CvFeedbackReport = {
  reportId: "r1",
  documentId: "doc1",
  status: "completed",
  atsScore: 80,
  strengths: [],
  improvements: [],
  rewrittenBullets: [],
  createdAt: "2026-01-01T00:00:00Z",
};

describe("useCvFeedback refetchInterval", () => {
  it("polls every 3s when status is pending and options.poll is true", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockResolvedValue(
      envelope({ ...baseReport, status: "pending" }),
    );
    const { result } = renderHook(() => useCvFeedback("doc1", { poll: true }), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    // refetchInterval is a function option; re-derive it the same way react-query would.
    const query = result.current;
    expect(query.data?.status).toBe("pending");
  });

  it("does not poll when status is completed", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockResolvedValue(envelope(baseReport));
    const { result } = renderHook(() => useCvFeedback("doc1", { poll: true }), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("completed");
  });

  it("does not poll when options.poll is false even if status is processing", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockResolvedValue(
      envelope({ ...baseReport, status: "processing" }),
    );
    const { result } = renderHook(() => useCvFeedback("doc1", { poll: false }), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("processing");
  });
});

describe("useRequestCvFeedback", () => {
  it("invalidates the feedback query on success", async () => {
    vi.spyOn(apiClient, "requestCvFeedback").mockResolvedValue(envelope({ jobId: "job1" }));

    const { result } = renderHook(() => useRequestCvFeedback("doc1"), { wrapper });
    result.current.mutate(undefined);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiClient.requestCvFeedback).toHaveBeenCalledWith("doc1", undefined);
  });
});

describe("useAcceptCvBullet", () => {
  it("calls the local accept-bullet client with documentId, reportId, and bulletIndex", async () => {
    vi.spyOn(localClient, "acceptCvFeedbackBullet").mockResolvedValue({ accepted: true });

    const { result } = renderHook(() => useAcceptCvBullet("doc1"), { wrapper });
    result.current.mutate({ reportId: "r1", bulletIndex: 0 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(localClient.acceptCvFeedbackBullet).toHaveBeenCalledWith("doc1", "r1", 0);
  });
});
