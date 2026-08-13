import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { CvFeedbackPanel } from "./CvFeedbackPanel";
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

const completedReport: CvFeedbackReport = {
  reportId: "r1",
  documentId: "doc1",
  status: "completed",
  atsScore: 75,
  strengths: ["Strong technical background"],
  improvements: ["Add more quantified results"],
  rewrittenBullets: [
    { original: "Worked on backend systems", rewritten: "Built backend systems serving 1M+ users", rationale: "Quantifies impact" },
  ],
  createdAt: "2026-01-01T00:00:00Z",
};

describe("CvFeedbackPanel", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows the 'Get AI feedback' button when there is no report", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockRejectedValue(new Error("404"));
    render(<CvFeedbackPanel documentId="doc1" />, { wrapper });
    expect(await screen.findByRole("button", { name: "Get AI feedback" })).toBeInTheDocument();
  });

  it("falls back to the request button when status is failed", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockResolvedValue(
      envelope({ ...completedReport, status: "failed" }),
    );
    render(<CvFeedbackPanel documentId="doc1" />, { wrapper });
    expect(await screen.findByRole("button", { name: "Get AI feedback" })).toBeInTheDocument();
  });

  it("shows an analyzing message when pending/processing", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockResolvedValue(
      envelope({ ...completedReport, status: "processing" }),
    );
    render(<CvFeedbackPanel documentId="doc1" />, { wrapper });
    expect(await screen.findByText("Analyzing your CV...")).toBeInTheDocument();
  });

  it("renders score, strengths, and rewritten bullets when completed", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockResolvedValue(envelope(completedReport));
    render(<CvFeedbackPanel documentId="doc1" />, { wrapper });

    expect(await screen.findByText("75/100")).toBeInTheDocument();
    expect(screen.getByText("Strong technical background")).toBeInTheDocument();
    expect(screen.getByText("Built backend systems serving 1M+ users")).toBeInTheDocument();
  });

  it("calls acceptBullet with correct reportId and bulletIndex on click", async () => {
    vi.spyOn(apiClient, "fetchCvFeedback").mockResolvedValue(envelope(completedReport));
    vi.spyOn(localClient, "acceptCvFeedbackBullet").mockResolvedValue({ accepted: true });

    render(<CvFeedbackPanel documentId="doc1" />, { wrapper });

    const useButton = await screen.findByRole("button", { name: "Use this version" });
    fireEvent.click(useButton);

    await waitFor(() =>
      expect(localClient.acceptCvFeedbackBullet).toHaveBeenCalledWith("doc1", "r1", 0),
    );
  });
});
