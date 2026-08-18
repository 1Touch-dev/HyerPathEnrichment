import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useDeleteDocument } from "./useDeleteDocument";
import { useReprocessDocument } from "./useReprocessDocument";
import { useDocumentSearch } from "./useDocumentSearch";
import * as client from "../api/client";
import { documentKeys } from "../api/keys";
import type { DocumentSearchResponse, DocumentUploadResult } from "@/src/lib/types";

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return { queryClient, wrapper };
}

const sampleReprocessResult: DocumentUploadResult = {
  jobId: "job2",
  documentId: "doc1",
  message: "Reprocessing started",
};

const sampleSearchResponse: DocumentSearchResponse = {
  results: [
    {
      documentId: "doc1",
      similarityScore: 0.92,
      cvData: { name: "Jane Doe" },
      excerpt: "Experienced engineer...",
    },
  ],
};

describe("useDeleteDocument", () => {
  it("deletes a document and invalidates the document list", async () => {
    vi.spyOn(client, "deleteDocument").mockResolvedValue(undefined);
    const { queryClient, wrapper } = createWrapper();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useDeleteDocument(), { wrapper });
    result.current.mutate("doc1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.deleteDocument).toHaveBeenCalledWith("doc1");
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: documentKeys.list() });
  });

  it("surfaces an error when the delete fails", async () => {
    vi.spyOn(client, "deleteDocument").mockRejectedValue(
      new Error("Failed to delete document: 500"),
    );
    const { wrapper } = createWrapper();

    const { result } = renderHook(() => useDeleteDocument(), { wrapper });
    result.current.mutate("doc1");

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("useReprocessDocument", () => {
  it("reprocesses a document and invalidates its detail query", async () => {
    vi.spyOn(client, "reprocessDocument").mockResolvedValue(sampleReprocessResult);
    const { queryClient, wrapper } = createWrapper();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useReprocessDocument(), { wrapper });
    result.current.mutate("doc1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.reprocessDocument).toHaveBeenCalledWith("doc1");
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: documentKeys.detail("doc1") });
  });

  it("surfaces an error when reprocessing fails", async () => {
    vi.spyOn(client, "reprocessDocument").mockRejectedValue(
      new Error("Failed to reprocess document: 500"),
    );
    const { wrapper } = createWrapper();

    const { result } = renderHook(() => useReprocessDocument(), { wrapper });
    result.current.mutate("doc1");

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("useDocumentSearch", () => {
  it("returns search results on success", async () => {
    vi.spyOn(client, "searchDocuments").mockResolvedValue(sampleSearchResponse);
    const { wrapper } = createWrapper();

    const { result } = renderHook(() => useDocumentSearch("engineer", 10), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(1);
    expect(client.searchDocuments).toHaveBeenCalledWith("engineer", 10);
  });

  it("surfaces an error when the search fails", async () => {
    vi.spyOn(client, "searchDocuments").mockRejectedValue(
      new Error("Failed to search documents: 500"),
    );
    const { wrapper } = createWrapper();

    const { result } = renderHook(() => useDocumentSearch("engineer", 10), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("does not search when the query is blank", () => {
    const searchDocuments = vi.spyOn(client, "searchDocuments");
    const { wrapper } = createWrapper();

    const { result } = renderHook(() => useDocumentSearch("   ", 10), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(searchDocuments).not.toHaveBeenCalled();
  });
});
