import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { DocumentsModerationPanel } from "./DocumentsModerationPanel";
import * as useDocumentsModerationHooks from "../hooks/useDocumentsModeration";
import type { AdminDocument, AdminDocumentListResponse } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const activeDocument: AdminDocument = {
  id: "d1",
  userId: "u1",
  documentType: "cv",
  originalFilename: "resume.pdf",
  mimeType: "application/pdf",
  fileSizeBytes: 1024,
  processingStatus: "completed",
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
  deletedAt: null,
};

const deletedDocument: AdminDocument = {
  ...activeDocument,
  id: "d2",
  originalFilename: "cover-letter.pdf",
  deletedAt: "2026-01-02T00:00:00Z",
};

const sampleList: AdminDocumentListResponse = {
  items: [activeDocument],
  nextCursor: null,
  hasMore: false,
};

function mockUseAdminDocuments(overrides: Partial<UseQueryResult<AdminDocumentListResponse>> = {}) {
  vi.spyOn(useDocumentsModerationHooks, "useAdminDocuments").mockReturnValue({
    data: sampleList,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<AdminDocumentListResponse>);
}

const moderateMutate = vi.fn();

function mockModerateDocument(overrides: Partial<ReturnType<typeof useDocumentsModerationHooks.useModerateDocument>> = {}) {
  vi.spyOn(useDocumentsModerationHooks, "useModerateDocument").mockReturnValue({
    mutate: moderateMutate,
    isPending: false,
    ...overrides,
  } as unknown as ReturnType<typeof useDocumentsModerationHooks.useModerateDocument>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  moderateMutate.mockReset();
  mockUseAdminDocuments();
  mockModerateDocument();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("DocumentsModerationPanel", () => {
  it("renders a row per document with filename, type, and status badges", () => {
    render(<DocumentsModerationPanel />, { wrapper });
    expect(screen.getByText("resume.pdf")).toBeInTheDocument();
    expect(screen.getByText("cv")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders an empty state when there are no documents", () => {
    mockUseAdminDocuments({ data: { items: [], nextCursor: null, hasMore: false } });
    render(<DocumentsModerationPanel />, { wrapper });
    expect(screen.getByText("No documents found")).toBeInTheDocument();
  });

  it("shows Deleted badge and a Restore action for a soft-deleted document", () => {
    mockUseAdminDocuments({ data: { items: [deletedDocument], nextCursor: null, hasMore: false } });
    render(<DocumentsModerationPanel />, { wrapper });
    expect(screen.getByText("Deleted")).toBeInTheDocument();
    expect(screen.getByText("Restore")).toBeInTheDocument();
  });

  it("calls useModerateDocument with soft_delete when Soft-delete is clicked, after confirmation", () => {
    render(<DocumentsModerationPanel />, { wrapper });
    fireEvent.click(screen.getByText("Soft-delete"));
    expect(moderateMutate).toHaveBeenCalledWith({ documentId: "d1", action: "soft_delete" });
  });

  it("calls useModerateDocument with restore when Restore is clicked, after confirmation", () => {
    mockUseAdminDocuments({ data: { items: [deletedDocument], nextCursor: null, hasMore: false } });
    render(<DocumentsModerationPanel />, { wrapper });
    fireEvent.click(screen.getByText("Restore"));
    expect(moderateMutate).toHaveBeenCalledWith({ documentId: "d2", action: "restore" });
  });

  it("does not call useModerateDocument when the confirmation is declined", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<DocumentsModerationPanel />, { wrapper });
    fireEvent.click(screen.getByText("Soft-delete"));
    expect(moderateMutate).not.toHaveBeenCalled();
  });

  it("disables the Next page button when hasMore is false", () => {
    render(<DocumentsModerationPanel />, { wrapper });
    expect(screen.getByText("Next page")).toBeDisabled();
  });

  it("enables the Next page button when hasMore is true", () => {
    mockUseAdminDocuments({ data: { items: [activeDocument], nextCursor: "cursor2", hasMore: true } });
    render(<DocumentsModerationPanel />, { wrapper });
    expect(screen.getByText("Next page")).not.toBeDisabled();
  });
});
