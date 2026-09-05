import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  useAcceptCvBullet,
  useCvFeedback,
  useCvFeedbackJobStatus,
  useRequestCvFeedback,
} from "./useCvFeedback";
import * as apiClient from "@/src/lib/api-client";
import { adaptCvFeedbackReport, adaptDocumentJobStatus } from "@/src/lib/api-adapter";
import { ApiError } from "@/src/lib/api-envelope";
import type { SuccessEnvelope } from "@/src/lib/api-envelope";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function envelope<T>(data: T): SuccessEnvelope<T> {
  return { success: true, data, message: null, meta: null };
}

// Realistic raw backend payloads (backend/app/modules/documents/schemas.py's
// `CvFeedbackResponse`/`JobStatusResponse`) run through the real adapters — not
// hand-typed frontend objects with a fake `status` field that doesn't exist on
// either backend response.
const rawCompletedReport = {
  report_id: "r1",
  document_id: "doc1",
  target_role: null,
  ats_score: 80,
  strengths: ["Strong technical background"],
  improvements: [],
  rewritten_bullets: [],
  accepted_bullet_indices: [],
  created_at: "2026-01-01T00:00:00Z",
};

const completedReport = adaptCvFeedbackReport(rawCompletedReport);

function rawJobStatus(status: string) {
  return {
    job_id: "job1",
    status,
    progress: status === "completed" ? 100 : 0,
    document_id: "doc1",
    result: status === "completed" ? { report_id: "r1" } : null,
    error: status === "failed" ? "boom" : null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

describe("useCvFeedback", () => {
  it("returns the adapted report when the backend has one", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockResolvedValue(envelope(completedReport));
    const { result } = renderHook(() => useCvFeedback("doc1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(completedReport);
  });

  it("resolves to null (not an error) when the backend 404s — no report yet", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockRejectedValue(
      new ApiError("No feedback report yet", { code: "NOT_FOUND", statusCode: 404 }),
    );
    const { result } = renderHook(() => useCvFeedback("doc1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });

  it("surfaces non-404 errors as query errors", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockRejectedValue(
      new ApiError("boom", { code: "INTERNAL_ERROR", statusCode: 500 }),
    );
    const { result } = renderHook(() => useCvFeedback("doc1"), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("useCvFeedbackJobStatus", () => {
  it("is disabled (no fetch) when jobId is null", () => {
    const spy = vi.spyOn(apiClient, "fetchDocumentJobStatus");
    const { result } = renderHook(() => useCvFeedbackJobStatus(null), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(spy).not.toHaveBeenCalled();
  });

  it("fetches and adapts the real job-status response for a pending job", async () => {
    vi.spyOn(apiClient, "fetchDocumentJobStatus").mockResolvedValue(
      envelope(adaptDocumentJobStatus(rawJobStatus("pending"))),
    );
    const { result } = renderHook(() => useCvFeedbackJobStatus("job1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("pending");
  });

  it("stops polling once the job reaches a terminal state", async () => {
    vi.spyOn(apiClient, "fetchDocumentJobStatus").mockResolvedValue(
      envelope(adaptDocumentJobStatus(rawJobStatus("completed"))),
    );
    const { result } = renderHook(() => useCvFeedbackJobStatus("job1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("completed");
  });
});

describe("useRequestCvFeedback", () => {
  it("resolves with the real job id returned by the backend enqueue response", async () => {
    vi.spyOn(apiClient, "requestCvFeedback").mockResolvedValue(envelope({ jobId: "job1" }));

    const { result } = renderHook(() => useRequestCvFeedback("doc1"), { wrapper });
    result.current.mutate(undefined);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiClient.requestCvFeedback).toHaveBeenCalledWith("doc1", undefined);
    expect(result.current.data).toEqual({ jobId: "job1" });
  });
});

describe("useAcceptCvBullet", () => {
  it("calls the shared acceptCvBullet client with documentId, reportId, and bulletIndex", async () => {
    vi.spyOn(apiClient, "acceptCvBullet").mockResolvedValue(envelope({ accepted: true }));

    const { result } = renderHook(() => useAcceptCvBullet("doc1"), { wrapper });
    result.current.mutate({ reportId: "r1", bulletIndex: 0 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiClient.acceptCvBullet).toHaveBeenCalledWith("doc1", "r1", 0);
  });
});
