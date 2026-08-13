import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { CvFeedbackPanel } from "./CvFeedbackPanel";
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
// `CvFeedbackResponse`/`JobStatusResponse`), run through the real adapters — this
// exercises `adaptCvFeedbackReport`/`adaptDocumentJobStatus` instead of hand-typing
// frontend-shaped fixtures with fields (like the old fake `status`) that never
// existed on the real backend response.
const rawCompletedReport = {
  report_id: "r1",
  document_id: "doc1",
  target_role: null,
  ats_score: 75,
  strengths: ["Strong technical background"],
  improvements: ["Add more quantified results"],
  rewritten_bullets: [
    { original: "Worked on backend systems", rewritten: "Built backend systems serving 1M+ users", rationale: "Quantifies impact" },
  ],
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

describe("CvFeedbackPanel", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows the 'Get AI feedback' button when the backend 404s (no report yet)", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockRejectedValue(
      new ApiError("No feedback report yet", { code: "NOT_FOUND", statusCode: 404 }),
    );
    render(<CvFeedbackPanel documentId="doc1" />, { wrapper });
    expect(await screen.findByRole("button", { name: "Get AI feedback" })).toBeInTheDocument();
  });

  it("shows an analyzing message and polls the real job-status endpoint after requesting feedback", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockRejectedValue(
      new ApiError("No feedback report yet", { code: "NOT_FOUND", statusCode: 404 }),
    );
    vi.spyOn(apiClient, "requestCvFeedback").mockResolvedValue(envelope({ jobId: "job1" }));
    vi.spyOn(apiClient, "fetchDocumentJobStatus").mockResolvedValue(
      envelope(adaptDocumentJobStatus(rawJobStatus("processing"))),
    );

    render(<CvFeedbackPanel documentId="doc1" />, { wrapper });

    fireEvent.click(await screen.findByRole("button", { name: "Get AI feedback" }));

    expect(await screen.findByText("Analyzing your CV...")).toBeInTheDocument();
    await waitFor(() => expect(apiClient.fetchDocumentJobStatus).toHaveBeenCalledWith("job1"));
  });

  it("refetches and renders the report once the job status reaches completed", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback")
      .mockRejectedValueOnce(new ApiError("No feedback report yet", { code: "NOT_FOUND", statusCode: 404 }))
      .mockResolvedValue(envelope(completedReport));
    vi.spyOn(apiClient, "requestCvFeedback").mockResolvedValue(envelope({ jobId: "job1" }));
    vi.spyOn(apiClient, "fetchDocumentJobStatus").mockResolvedValue(
      envelope(adaptDocumentJobStatus(rawJobStatus("completed"))),
    );

    render(<CvFeedbackPanel documentId="doc1" />, { wrapper });

    fireEvent.click(await screen.findByRole("button", { name: "Get AI feedback" }));

    expect(await screen.findByText("75/100")).toBeInTheDocument();
  });

  it("renders score, strengths, and rewritten bullets when a report already exists", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockResolvedValue(envelope(completedReport));
    render(<CvFeedbackPanel documentId="doc1" />, { wrapper });

    expect(await screen.findByText("75/100")).toBeInTheDocument();
    expect(screen.getByText("Strong technical background")).toBeInTheDocument();
    expect(screen.getByText("Built backend systems serving 1M+ users")).toBeInTheDocument();
  });

  it("calls acceptBullet with correct reportId and bulletIndex on click", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockResolvedValue(envelope(completedReport));
    vi.spyOn(apiClient, "acceptCvBullet").mockResolvedValue(envelope({ accepted: true }));

    render(<CvFeedbackPanel documentId="doc1" />, { wrapper });

    const useButton = await screen.findByRole("button", { name: "Use this version" });
    fireEvent.click(useButton);

    await waitFor(() =>
      expect(apiClient.acceptCvBullet).toHaveBeenCalledWith("doc1", "r1", 0),
    );
  });
});
