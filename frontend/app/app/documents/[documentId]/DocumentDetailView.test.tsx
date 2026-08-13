import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { DocumentDetailView } from "./DocumentDetailView";
import * as apiClient from "@/src/lib/api-client";
import type { CvChatSession, CvCompleteness, CvFeedbackReport } from "@/src/lib/types";
import type { SuccessEnvelope } from "@/src/lib/api-envelope";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function envelope<T>(data: T): SuccessEnvelope<T> {
  return { success: true, data, message: null, meta: null };
}

const incompleteCompleteness: CvCompleteness = {
  documentId: "doc1",
  completenessScore: 0.5,
  missingFields: ["phone"],
  hasActiveChatSession: false,
};

const activeSession: CvChatSession = {
  sessionId: "s1",
  status: "active",
  missingFieldsAtStart: ["phone"],
  fieldsResolved: [],
  messages: [{ id: "m1", role: "assistant", content: "What is your phone number?", createdAt: "2026-01-01T00:00:00Z" }],
};

const pendingFeedback: CvFeedbackReport = {
  reportId: "r1",
  documentId: "doc1",
  targetRole: null,
  atsScore: 0,
  strengths: [],
  improvements: [],
  rewrittenBullets: [],
  acceptedBulletIndices: [],
  createdAt: "2026-01-01T00:00:00Z",
};

describe("DocumentDetailView", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "fetchCvFeedback").mockResolvedValue(envelope(pendingFeedback));
  });

  it("does not render CvChatWidget until onStartChat fires from CompletenessBanner", async () => {
    vi.spyOn(apiClient, "fetchCvCompleteness").mockResolvedValue(envelope(incompleteCompleteness));

    render(<DocumentDetailView documentId="doc1" />, { wrapper });

    expect(screen.queryByRole("button", { name: "Start CV completeness chat" })).not.toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: "Complete it" }));

    expect(await screen.findByRole("button", { name: "Start CV completeness chat" })).toBeInTheDocument();
  });

  it("unmounts CvChatWidget again once onComplete fires", async () => {
    vi.spyOn(apiClient, "fetchCvCompleteness").mockResolvedValue(envelope(incompleteCompleteness));
    vi.spyOn(apiClient, "startCvChatSession").mockResolvedValue(envelope(activeSession));
    vi.spyOn(apiClient, "postCvChatMessage").mockResolvedValue(
      envelope({ ...activeSession, status: "completed" }),
    );

    render(<DocumentDetailView documentId="doc1" />, { wrapper });

    fireEvent.click(await screen.findByRole("button", { name: "Complete it" }));
    fireEvent.click(await screen.findByRole("button", { name: "Start CV completeness chat" }));

    const input = await screen.findByPlaceholderText("Type your answer...");
    fireEvent.change(input, { target: { value: "555-1234" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(screen.queryByPlaceholderText("Type your answer...")).not.toBeInTheDocument(),
    );
  });
});
