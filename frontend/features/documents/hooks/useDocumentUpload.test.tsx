import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useUploadDocument } from "./useUploadDocument";
import { useDocumentJobQuery } from "./useDocumentJobQuery";
import * as client from "../api/client";
import type { DocumentJobStatus, DocumentUploadResult } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleUploadResult: DocumentUploadResult = {
  jobId: "job1",
  documentId: "doc1",
  message: "Upload accepted",
};

const processingJob: DocumentJobStatus = {
  jobId: "job1",
  status: "processing",
  progress: 40,
  documentId: "doc1",
  result: null,
  error: null,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

const completedJob: DocumentJobStatus = {
  ...processingJob,
  status: "completed",
  progress: 100,
  result: { name: "Jane Doe" },
};

describe("useUploadDocument", () => {
  it("uploads a file and returns the upload result", async () => {
    vi.spyOn(client, "uploadDocument").mockResolvedValue(sampleUploadResult);
    const file = new File(["cv content"], "resume.pdf", { type: "application/pdf" });

    const { result } = renderHook(() => useUploadDocument(), { wrapper });
    result.current.mutate({ file, documentType: "cv" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.uploadDocument).toHaveBeenCalledWith(file, "cv");
    expect(result.current.data).toEqual(sampleUploadResult);
  });

  it("surfaces an error when the upload fails", async () => {
    vi.spyOn(client, "uploadDocument").mockRejectedValue(
      new Error("Failed to upload document: 500"),
    );
    const file = new File(["cv content"], "resume.pdf", { type: "application/pdf" });

    const { result } = renderHook(() => useUploadDocument(), { wrapper });
    result.current.mutate({ file, documentType: "cv" });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("useDocumentJobQuery", () => {
  it("returns job status data on success", async () => {
    vi.spyOn(client, "fetchDocumentJob").mockResolvedValue(processingJob);

    const { result } = renderHook(() => useDocumentJobQuery("job1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("processing");
    expect(client.fetchDocumentJob).toHaveBeenCalledWith("job1");
  });

  it("surfaces an error when the fetch fails", async () => {
    vi.spyOn(client, "fetchDocumentJob").mockRejectedValue(
      new Error("Failed to fetch document job: 404"),
    );

    const { result } = renderHook(() => useDocumentJobQuery("job1"), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("does not fetch when jobId is undefined", () => {
    const fetchDocumentJob = vi.spyOn(client, "fetchDocumentJob");

    const { result } = renderHook(() => useDocumentJobQuery(undefined), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(fetchDocumentJob).not.toHaveBeenCalled();
  });

  it("keeps polling while the job is still in a non-terminal status", async () => {
    const fetchDocumentJob = vi.spyOn(client, "fetchDocumentJob").mockResolvedValue(processingJob);

    renderHook(() => useDocumentJobQuery("job1"), { wrapper });

    await waitFor(() => expect(fetchDocumentJob).toHaveBeenCalledTimes(2), { timeout: 6000 });
  }, 8000);

  it("stops polling once a terminal status is reached", async () => {
    const fetchDocumentJob = vi.spyOn(client, "fetchDocumentJob").mockResolvedValue(completedJob);

    const { result } = renderHook(() => useDocumentJobQuery("job1"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("completed");

    // refetchInterval must resolve to `false` once the terminal status is
    // observed, so no further calls should arrive even after waiting past
    // another poll interval (POLL_INTERVAL_MS = 2000ms in the hook).
    await new Promise((resolve) => setTimeout(resolve, 2500));
    expect(fetchDocumentJob).toHaveBeenCalledTimes(1);
  }, 8000);
});
