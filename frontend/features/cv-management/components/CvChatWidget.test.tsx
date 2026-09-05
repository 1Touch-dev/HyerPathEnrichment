import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { CvChatWidget } from "./CvChatWidget";
import * as apiClient from "@/src/lib/api-client";
import type { CvChatSession } from "@/src/lib/types";
import type { SuccessEnvelope } from "@/src/lib/api-envelope";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function envelope<T>(data: T): SuccessEnvelope<T> {
  return { success: true, data, message: null, meta: null };
}

const activeSession: CvChatSession = {
  sessionId: "s1",
  status: "active",
  missingFieldsAtStart: ["phone"],
  fieldsResolved: [],
  messages: [
    {
      id: "m1",
      role: "assistant",
      content: "What is your phone number?",
      createdAt: "2026-01-01T00:00:00Z",
    },
    { id: "m2", role: "user", content: "555-1234", createdAt: "2026-01-01T00:01:00Z" },
  ],
};

describe("CvChatWidget", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows the start button when there is no session", () => {
    render(<CvChatWidget documentId="doc1" />, { wrapper });
    expect(screen.getByRole("button", { name: "Start CV completeness chat" })).toBeInTheDocument();
  });

  it("renders message bubbles aligned by role", async () => {
    vi.spyOn(apiClient, "startCvChatSession").mockResolvedValue(envelope(activeSession));
    render(<CvChatWidget documentId="doc1" />, { wrapper });

    fireEvent.click(screen.getByRole("button", { name: "Start CV completeness chat" }));

    const assistantMessage = await screen.findByText("What is your phone number?");
    expect(assistantMessage.closest("div")?.className).toContain("text-left");

    const userMessage = screen.getByText("555-1234");
    expect(userMessage.closest("div")?.className).toContain("text-right");
  });

  it("hides the input form and shows a completion message when status is completed", async () => {
    vi.spyOn(apiClient, "startCvChatSession").mockResolvedValue(
      envelope({ ...activeSession, status: "completed" }),
    );
    render(<CvChatWidget documentId="doc1" />, { wrapper });
    fireEvent.click(screen.getByRole("button", { name: "Start CV completeness chat" }));

    expect(await screen.findByText("All done — your CV is up to date.")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Type your answer...")).not.toBeInTheDocument();
  });

  it("fires onComplete when sendMessage response has status completed", async () => {
    vi.spyOn(apiClient, "startCvChatSession").mockResolvedValue(envelope(activeSession));
    vi.spyOn(apiClient, "postCvChatMessage").mockResolvedValue(
      envelope({ ...activeSession, status: "completed" }),
    );
    const onComplete = vi.fn();
    render(<CvChatWidget documentId="doc1" onComplete={onComplete} />, { wrapper });

    fireEvent.click(screen.getByRole("button", { name: "Start CV completeness chat" }));
    const input = await screen.findByPlaceholderText("Type your answer...");
    fireEvent.change(input, { target: { value: "555-1234" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
  });
});
