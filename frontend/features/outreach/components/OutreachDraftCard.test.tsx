import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { OutreachDraftCard } from "./OutreachDraftCard";
import * as apiClient from "@/src/lib/api-client";
import type { OutreachMessage } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const draftMessage: OutreachMessage = {
  messageId: "msg1",
  jobPostingId: "jp1",
  companyName: "Acme",
  recipientRole: "Hiring Manager",
  subject: "Excited about the role",
  body: "Hello there",
  status: "draft",
  companyContextSource: "perplexity",
  createdAt: "2026-01-01T00:00:00Z",
  sentAt: null,
};

describe("OutreachDraftCard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "editOutreachDraft").mockResolvedValue({
      success: true,
      data: { ...draftMessage, subject: "Edited subject" },
    });
    vi.spyOn(apiClient, "sendOutreach").mockResolvedValue({
      success: true,
      data: { ...draftMessage, status: "sent" },
    });
  });

  it("keeps subject/body inputs editable while status is 'draft'", () => {
    render(<OutreachDraftCard message={draftMessage} />, { wrapper });
    expect(screen.getByDisplayValue(draftMessage.subject)).not.toBeDisabled();
    expect(screen.getByDisplayValue(draftMessage.body)).not.toBeDisabled();
  });

  it("disables subject/body inputs once status is not 'draft'", () => {
    render(<OutreachDraftCard message={{ ...draftMessage, status: "sent" }} />, { wrapper });
    expect(screen.getByDisplayValue(draftMessage.subject)).toBeDisabled();
    expect(screen.getByDisplayValue(draftMessage.body)).toBeDisabled();
  });

  it('shows "Save changes" only once the text differs from the original message props', () => {
    render(<OutreachDraftCard message={draftMessage} />, { wrapper });
    expect(screen.queryByText("Save changes")).not.toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue(draftMessage.subject), {
      target: { value: "A new subject" },
    });
    expect(screen.getByText("Save changes")).toBeInTheDocument();
  });

  it('disables "Send" while dirty and enables it once saved', async () => {
    render(<OutreachDraftCard message={draftMessage} />, { wrapper });
    const sendButton = screen.getByText("Send");
    expect(sendButton).not.toBeDisabled();

    fireEvent.change(screen.getByDisplayValue(draftMessage.subject), {
      target: { value: "A new subject" },
    });
    expect(screen.getByText("Send")).toBeDisabled();

    fireEvent.click(screen.getByText("Save changes"));
    await waitFor(() => expect(apiClient.editOutreachDraft).toHaveBeenCalled());
  });

  it('shows the "Generic draft" badge only when companyContextSource is "none"', () => {
    render(<OutreachDraftCard message={{ ...draftMessage, companyContextSource: "none" }} />, { wrapper });
    expect(screen.getByText("Generic draft")).toBeInTheDocument();
  });

  it('hides the "Generic draft" badge when companyContextSource is "perplexity"', () => {
    render(<OutreachDraftCard message={draftMessage} />, { wrapper });
    expect(screen.queryByText("Generic draft")).not.toBeInTheDocument();
  });
});
