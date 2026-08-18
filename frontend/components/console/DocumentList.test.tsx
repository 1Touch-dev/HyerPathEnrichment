import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { DocumentList } from "./DocumentList";
import * as client from "../../features/documents/api/client";
import type { CandidateDocument } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleDocuments: CandidateDocument[] = [
  {
    documentId: "doc-1",
    documentType: "cv",
    originalFilename: "resume.pdf",
    fileSizeBytes: 1024,
    processingStatus: "completed",
    createdAt: "2026-01-01T12:00:00Z",
  },
];

describe("DocumentList", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(client, "deleteDocument").mockResolvedValue(undefined);
    vi.spyOn(client, "reprocessDocument").mockResolvedValue({
      jobId: "job-1",
      documentId: "doc-1",
      message: "Reprocessing started",
    });
  });

  it("renders the empty state when there are no documents", () => {
    render(<DocumentList documents={[]} />, { wrapper });
    expect(screen.getByText("No documents yet")).toBeInTheDocument();
  });

  it("renders document rows with filename, type, and status", () => {
    render(<DocumentList documents={sampleDocuments} />, { wrapper });
    expect(screen.getByText("resume.pdf")).toBeInTheDocument();
    expect(screen.getByText("CV")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("deletes the document after the user confirms", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<DocumentList documents={sampleDocuments} />, { wrapper });

    fireEvent.click(screen.getByRole("button", { name: /delete/i }));

    await waitFor(() => expect(client.deleteDocument).toHaveBeenCalledWith("doc-1"));
    expect(window.confirm).toHaveBeenCalledWith("Delete this document? This cannot be undone.");
  });

  it("does not delete the document when the user cancels the confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<DocumentList documents={sampleDocuments} />, { wrapper });

    fireEvent.click(screen.getByRole("button", { name: /delete/i }));

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(client.deleteDocument).not.toHaveBeenCalled();
  });

  it("reprocesses the document when the reprocess button is clicked", async () => {
    render(<DocumentList documents={sampleDocuments} />, { wrapper });

    fireEvent.click(screen.getByRole("button", { name: /reprocess/i }));

    await waitFor(() => expect(client.reprocessDocument).toHaveBeenCalledWith("doc-1"));
  });
});
