import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest";
import { render, screen, fireEvent, within, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ComponentProps, ReactNode } from "react";
import { DraftOutreachDialog } from "./DraftOutreachDialog";
import * as apiClient from "@/src/lib/api-client";

// Radix Select relies on pointer capture / scrollIntoView APIs jsdom doesn't implement.
beforeAll(() => {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.scrollIntoView = () => {};
});

vi.mock("@/features/job-matching/hooks/useMatches", () => ({
  useMatches: () => ({
    data: { matches: [], total: 0 },
    isLoading: false,
  }),
}));

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function renderDialog(
  props: Partial<ComponentProps<typeof DraftOutreachDialog>> & {
    onConfirm?: ReturnType<typeof vi.fn>;
  } = {},
) {
  const { onConfirm = vi.fn(), ...rest } = props;
  return render(
    <DraftOutreachDialog
      open
      companyName="Acme"
      onOpenChange={() => {}}
      onConfirm={onConfirm}
      {...rest}
    />,
    { wrapper },
  );
}

async function selectMessageType(label: string) {
  fireEvent.click(screen.getByLabelText("Message type"));
  const listbox = await screen.findByRole("listbox");
  fireEvent.click(within(listbox).getByText(label));
}

async function waitForResumeReady() {
  await waitFor(() => {
    expect(screen.getByText(/Using: resume\.pdf/i)).toBeInTheDocument();
  });
}

describe("DraftOutreachDialog", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "fetchDocuments").mockResolvedValue({
      success: true,
      data: [
        {
          documentId: "doc-1",
          documentType: "cv",
          originalFilename: "resume.pdf",
          fileSizeBytes: 12345,
          processingStatus: "completed",
          createdAt: "2026-01-01T00:00:00Z",
        },
      ],
    });
  });

  it("does not render the custom-instruction textarea by default (Email selected)", async () => {
    renderDialog();
    await waitForResumeReady();
    expect(screen.queryByLabelText("Instructions for this message")).not.toBeInTheDocument();
  });

  it('renders the custom-instruction textarea only when "Custom" is selected', async () => {
    renderDialog();
    await waitForResumeReady();

    await selectMessageType("Custom");

    expect(screen.getByLabelText("Instructions for this message")).toBeInTheDocument();
  });

  it("disables confirm until custom instruction text is entered when Custom is selected", async () => {
    renderDialog();
    await waitForResumeReady();

    await selectMessageType("Custom");

    const confirmButton = screen.getByRole("button", { name: "Draft outreach" });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Instructions for this message"), {
      target: { value: "Mention the referral from Jane." },
    });
    expect(confirmButton).not.toBeDisabled();
  });

  it("hides the custom-instruction textarea again after switching away from Custom", async () => {
    renderDialog();
    await waitForResumeReady();

    await selectMessageType("Custom");
    expect(screen.getByLabelText("Instructions for this message")).toBeInTheDocument();

    await selectMessageType("Email");
    expect(screen.queryByLabelText("Instructions for this message")).not.toBeInTheDocument();
  });

  it("calls onConfirm with messageType, documentId, and company for non-custom types", async () => {
    const onConfirm = vi.fn();
    renderDialog({ onConfirm });
    await waitForResumeReady();

    await selectMessageType("LinkedIn message");
    fireEvent.click(screen.getByRole("button", { name: "Draft outreach" }));

    expect(onConfirm).toHaveBeenCalledWith({
      messageType: "linkedin",
      customInstruction: undefined,
      documentId: "doc-1",
      companyName: "Acme",
      recipientRoleTitle: undefined,
    });
  });

  it("calls onConfirm with the trimmed customInstruction when Custom is selected", async () => {
    const onConfirm = vi.fn();
    renderDialog({ onConfirm });
    await waitForResumeReady();

    await selectMessageType("Custom");
    fireEvent.change(screen.getByLabelText("Instructions for this message"), {
      target: { value: "  Mention the referral from Jane.  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Draft outreach" }));

    expect(onConfirm).toHaveBeenCalledWith({
      messageType: "custom",
      customInstruction: "Mention the referral from Jane.",
      documentId: "doc-1",
      companyName: "Acme",
      recipientRoleTitle: undefined,
    });
  });

  it("includes pasted jobDescription when Paste JD is selected", async () => {
    const onConfirm = vi.fn();
    renderDialog({ onConfirm });
    await waitForResumeReady();

    fireEvent.click(screen.getByLabelText("Paste JD"));
    const jd =
      "We are hiring a backend engineer with strong Python experience and distributed systems skills.";
    fireEvent.change(screen.getByLabelText("Job description"), {
      target: { value: jd },
    });
    fireEvent.click(screen.getByRole("button", { name: "Draft outreach" }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        documentId: "doc-1",
        companyName: "Acme",
        jobDescription: jd,
      }),
    );
  });

  it("disables confirm when paste JD is under 50 characters", async () => {
    renderDialog();
    await waitForResumeReady();

    fireEvent.click(screen.getByLabelText("Paste JD"));
    fireEvent.change(screen.getByLabelText("Job description"), {
      target: { value: "too short" },
    });
    expect(screen.getByRole("button", { name: "Draft outreach" })).toBeDisabled();
  });
});
