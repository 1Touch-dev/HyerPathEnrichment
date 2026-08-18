import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useDocuments } from "./useDocuments";
import { useDocument } from "./useDocument";
import { useCvData } from "./useCvData";
import * as client from "../api/client";
import type { CandidateDocument, CandidateDocumentDetail, CvData } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleDocumentList: CandidateDocument[] = [
  {
    documentId: "doc1",
    documentType: "cv",
    originalFilename: "resume.pdf",
    fileSizeBytes: 12345,
    processingStatus: "completed",
    createdAt: "2026-01-01T00:00:00Z",
  },
];

const sampleDocumentDetail: CandidateDocumentDetail = {
  documentId: "doc1",
  documentType: "cv",
  originalFilename: "resume.pdf",
  fileSizeBytes: 12345,
  processingStatus: "completed",
  rawText: "raw text content",
  extractedData: { name: "Jane Doe" },
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

const sampleCvData: CvData = {
  documentId: "doc1",
  extractedData: { name: "Jane Doe" },
  rawText: "raw text content",
  processingStatus: "completed",
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("useDocuments", () => {
  it("returns document list data on success", async () => {
    vi.spyOn(client, "fetchDocuments").mockResolvedValue(sampleDocumentList);

    const { result } = renderHook(() => useDocuments(50), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(client.fetchDocuments).toHaveBeenCalledWith(50);
  });

  it("surfaces an error when the fetch fails", async () => {
    vi.spyOn(client, "fetchDocuments").mockRejectedValue(
      new Error("Failed to fetch documents: 500"),
    );

    const { result } = renderHook(() => useDocuments(50), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("useDocument", () => {
  it("returns document detail data on success", async () => {
    vi.spyOn(client, "fetchDocument").mockResolvedValue(sampleDocumentDetail);

    const { result } = renderHook(() => useDocument("doc1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.originalFilename).toBe("resume.pdf");
    expect(client.fetchDocument).toHaveBeenCalledWith("doc1");
  });

  it("surfaces an error when the fetch fails", async () => {
    vi.spyOn(client, "fetchDocument").mockRejectedValue(new Error("Failed to fetch document: 404"));

    const { result } = renderHook(() => useDocument("doc1"), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("does not fetch when documentId is undefined", () => {
    const fetchDocument = vi.spyOn(client, "fetchDocument");

    const { result } = renderHook(() => useDocument(undefined), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(fetchDocument).not.toHaveBeenCalled();
  });
});

describe("useCvData", () => {
  it("returns CV data on success", async () => {
    vi.spyOn(client, "fetchCvData").mockResolvedValue(sampleCvData);

    const { result } = renderHook(() => useCvData("doc1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.extractedData).toEqual({ name: "Jane Doe" });
    expect(client.fetchCvData).toHaveBeenCalledWith("doc1");
  });

  it("surfaces an error when the fetch fails", async () => {
    vi.spyOn(client, "fetchCvData").mockRejectedValue(new Error("Failed to fetch CV data: 404"));

    const { result } = renderHook(() => useCvData("doc1"), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("does not fetch when documentId is undefined", () => {
    const fetchCvData = vi.spyOn(client, "fetchCvData");

    const { result } = renderHook(() => useCvData(undefined), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(fetchCvData).not.toHaveBeenCalled();
  });
});
