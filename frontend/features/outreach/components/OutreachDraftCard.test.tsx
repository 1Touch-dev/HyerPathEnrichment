import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { OutreachDraftCard } from "./OutreachDraftCard";
import * as apiClient from "@/src/lib/api-client";
import * as utils from "@/src/lib/utils";
import { ApiError } from "@/src/lib/api-envelope";
import type { OutreachMessage } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const draftMessage: OutreachMessage = {
  messageId: "msg1",
  companyName: "Acme",
  recipientRoleTitle: "Hiring Manager",
  subject: "Excited about the role",
  body: "Hello there",
  status: "draft",
  messageType: "email",
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

  it('relabels the send button to "Copy & mark as sent" and shows the copy-paste note for non-email types', () => {
    render(<OutreachDraftCard message={{ ...draftMessage, messageType: "linkedin" }} />, {
      wrapper,
    });
    expect(screen.getByText("Copy & mark as sent")).toBeInTheDocument();
    expect(screen.queryByText("Send", { selector: "button" })).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "LinkedIn/DMs can't be sent from here — copy this and paste it into LinkedIn/your messaging app yourself.",
      ),
    ).toBeInTheDocument();
  });

  it('keeps the "Send" copy unchanged for email messages', () => {
    render(<OutreachDraftCard message={draftMessage} />, { wrapper });
    expect(screen.getByText("Send")).toBeInTheDocument();
    expect(screen.queryByText("Copy & mark as sent")).not.toBeInTheDocument();
  });

  it('renders a "Copy to clipboard" icon button with the correct aria-label for non-email types, and calls copyToClipboard with the body', () => {
    const copySpy = vi.spyOn(utils, "copyToClipboard").mockResolvedValue(undefined);
    render(<OutreachDraftCard message={{ ...draftMessage, messageType: "generic" }} />, {
      wrapper,
    });
    const copyButton = screen.getByRole("button", { name: "Copy message to clipboard" });
    fireEvent.click(copyButton);
    expect(copySpy).toHaveBeenCalledWith(draftMessage.body);
  });

  it("does not render the clipboard copy button for email messages", () => {
    render(<OutreachDraftCard message={draftMessage} />, { wrapper });
    expect(
      screen.queryByRole("button", { name: "Copy message to clipboard" }),
    ).not.toBeInTheDocument();
  });

  it('also copies the body to clipboard when "Copy & mark as sent" is clicked for non-email types', async () => {
    const copySpy = vi.spyOn(utils, "copyToClipboard").mockResolvedValue(undefined);
    render(<OutreachDraftCard message={{ ...draftMessage, messageType: "linkedin" }} />, {
      wrapper,
    });
    fireEvent.click(screen.getByText("Copy & mark as sent"));
    expect(copySpy).toHaveBeenCalledWith(draftMessage.body);
    await waitFor(() =>
      expect(apiClient.sendOutreach).toHaveBeenCalledWith(draftMessage.messageId),
    );
  });

  it("renders a LinkedIn character counter under subject and body, amber past 1500 and red past 1900 for the body", () => {
    render(<OutreachDraftCard message={{ ...draftMessage, messageType: "linkedin" }} />, {
      wrapper,
    });

    fireEvent.change(screen.getByDisplayValue(draftMessage.body), {
      target: { value: "a".repeat(1600) },
    });
    const amberCounter = screen.getByText("1600 / 1900");
    expect(amberCounter.className).toContain("amber");

    fireEvent.change(screen.getByDisplayValue("a".repeat(1600)), {
      target: { value: "a".repeat(1950) },
    });
    const redCounter = screen.getByText("1950 / 1900");
    expect(redCounter.className).toContain("red");
  });

  it("does not render a character counter for non-LinkedIn message types", () => {
    render(<OutreachDraftCard message={{ ...draftMessage, messageType: "generic" }} />, {
      wrapper,
    });
    expect(screen.queryByText(/\/ 1900/)).not.toBeInTheDocument();
  });

  it("surfaces a 422 edit-validation error near the save button instead of swallowing it", async () => {
    vi.spyOn(apiClient, "editOutreachDraft").mockRejectedValue(
      new ApiError(
        "LinkedIn messages are limited to 1900 characters; please shorten before saving",
        {
          code: "VALIDATION_ERROR",
          statusCode: 422,
        },
      ),
    );
    render(<OutreachDraftCard message={{ ...draftMessage, messageType: "linkedin" }} />, {
      wrapper,
    });

    fireEvent.change(screen.getByDisplayValue(draftMessage.body), {
      target: { value: "a longer body than before" },
    });
    fireEvent.click(screen.getByText("Save changes"));

    await waitFor(() =>
      expect(
        screen.getByText(
          "LinkedIn messages are limited to 1900 characters; please shorten before saving",
        ),
      ).toBeInTheDocument(),
    );
  });
});
