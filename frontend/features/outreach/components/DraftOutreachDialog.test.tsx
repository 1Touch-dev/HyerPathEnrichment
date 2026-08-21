import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { DraftOutreachDialog } from "./DraftOutreachDialog";

// Radix Select relies on pointer capture / scrollIntoView APIs jsdom doesn't implement.
beforeAll(() => {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.scrollIntoView = () => {};
});

async function selectMessageType(label: string) {
  fireEvent.click(screen.getByLabelText("Message type"));
  const listbox = await screen.findByRole("listbox");
  fireEvent.click(within(listbox).getByText(label));
}

describe("DraftOutreachDialog", () => {
  it("does not render the custom-instruction textarea by default (Email selected)", () => {
    render(
      <DraftOutreachDialog open companyName="Acme" onOpenChange={() => {}} onConfirm={() => {}} />,
    );
    expect(screen.queryByLabelText("Instructions for this message")).not.toBeInTheDocument();
  });

  it('renders the custom-instruction textarea only when "Custom" is selected', async () => {
    render(
      <DraftOutreachDialog open companyName="Acme" onOpenChange={() => {}} onConfirm={() => {}} />,
    );

    await selectMessageType("Custom");

    expect(screen.getByLabelText("Instructions for this message")).toBeInTheDocument();
  });

  it("disables confirm until custom instruction text is entered when Custom is selected", async () => {
    render(
      <DraftOutreachDialog open companyName="Acme" onOpenChange={() => {}} onConfirm={() => {}} />,
    );

    await selectMessageType("Custom");

    const confirmButton = screen.getByRole("button", { name: "Draft outreach" });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Instructions for this message"), {
      target: { value: "Mention the referral from Jane." },
    });
    expect(confirmButton).not.toBeDisabled();
  });

  it("hides the custom-instruction textarea again after switching away from Custom", async () => {
    render(
      <DraftOutreachDialog open companyName="Acme" onOpenChange={() => {}} onConfirm={() => {}} />,
    );

    await selectMessageType("Custom");
    expect(screen.getByLabelText("Instructions for this message")).toBeInTheDocument();

    await selectMessageType("Email");
    expect(screen.queryByLabelText("Instructions for this message")).not.toBeInTheDocument();
  });

  it("calls onConfirm with the selected messageType and no customInstruction for non-custom types", async () => {
    const onConfirm = vi.fn();
    render(
      <DraftOutreachDialog open companyName="Acme" onOpenChange={() => {}} onConfirm={onConfirm} />,
    );

    await selectMessageType("LinkedIn message");
    fireEvent.click(screen.getByRole("button", { name: "Draft outreach" }));

    expect(onConfirm).toHaveBeenCalledWith({
      messageType: "linkedin",
      customInstruction: undefined,
    });
  });

  it("calls onConfirm with the trimmed customInstruction when Custom is selected", async () => {
    const onConfirm = vi.fn();
    render(
      <DraftOutreachDialog open companyName="Acme" onOpenChange={() => {}} onConfirm={onConfirm} />,
    );

    await selectMessageType("Custom");
    fireEvent.change(screen.getByLabelText("Instructions for this message"), {
      target: { value: "  Mention the referral from Jane.  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Draft outreach" }));

    expect(onConfirm).toHaveBeenCalledWith({
      messageType: "custom",
      customInstruction: "Mention the referral from Jane.",
    });
  });
});
