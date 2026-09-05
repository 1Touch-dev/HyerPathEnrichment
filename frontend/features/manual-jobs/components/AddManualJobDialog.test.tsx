import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AddManualJobDialog } from "./AddManualJobDialog";
import * as client from "../api/client";
import { applicationTrackerKeys } from "@/features/application-tracker/api/keys";
import type { ManualJobEntry } from "@/src/lib/types";

function makeWrapper(queryClient: QueryClient) {
  return function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const sampleEntry: ManualJobEntry = {
  id: "entry1",
  title: "Senior Engineer",
  company: "Acme",
  location: "Remote",
  sourceLabel: "LinkedIn",
  sourceUrl: "https://example.com/careers/123",
  notes: null,
  jobMatchId: "m1",
  createdAt: "2026-01-01T00:00:00Z",
};

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText("Job title"), { target: { value: "Senior Engineer" } });
  fireEvent.change(screen.getByLabelText("Company"), { target: { value: "Acme" } });
}

describe("AddManualJobDialog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the dialog form fields when open", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<AddManualJobDialog open={true} onOpenChange={() => {}} />, {
      wrapper: makeWrapper(queryClient),
    });

    expect(screen.getByLabelText("Job title")).toBeInTheDocument();
    expect(screen.getByLabelText("Company")).toBeInTheDocument();
    expect(screen.getByLabelText("Location")).toBeInTheDocument();
    expect(screen.getByLabelText("Job posting URL")).toBeInTheDocument();
    expect(screen.getByLabelText("Notes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add job" })).toBeInTheDocument();
  });

  it("does not render dialog content when closed", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<AddManualJobDialog open={false} onOpenChange={() => {}} />, {
      wrapper: makeWrapper(queryClient),
    });

    expect(screen.queryByLabelText("Job title")).not.toBeInTheDocument();
  });

  it("blocks submission and shows an inline error when title/company are empty", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.spyOn(client, "createManualJobEntry").mockResolvedValue(sampleEntry);

    render(<AddManualJobDialog open={true} onOpenChange={() => {}} />, {
      wrapper: makeWrapper(queryClient),
    });

    fireEvent.click(screen.getByRole("button", { name: "Add job" }));

    expect(screen.getByText("Title and company are required.")).toBeInTheDocument();
    expect(client.createManualJobEntry).not.toHaveBeenCalled();
  });

  it("blocks submission and shows an inline error when the source URL is not a valid URL", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.spyOn(client, "createManualJobEntry").mockResolvedValue(sampleEntry);

    render(<AddManualJobDialog open={true} onOpenChange={() => {}} />, {
      wrapper: makeWrapper(queryClient),
    });

    fillRequiredFields();
    fireEvent.change(screen.getByLabelText("Job posting URL"), {
      target: { value: "not-a-url" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add job" }));

    expect(
      screen.getByText("Please enter a valid URL (e.g. https://example.com/careers/123)."),
    ).toBeInTheDocument();
    expect(client.createManualJobEntry).not.toHaveBeenCalled();
  });

  it("submits correctly-shaped data and invalidates the tracker query on success", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    vi.spyOn(client, "createManualJobEntry").mockResolvedValue(sampleEntry);
    const onOpenChange = vi.fn();

    render(<AddManualJobDialog open={true} onOpenChange={onOpenChange} />, {
      wrapper: makeWrapper(queryClient),
    });

    fillRequiredFields();
    fireEvent.change(screen.getByLabelText("Location"), { target: { value: "Remote" } });
    fireEvent.change(screen.getByLabelText("Job posting URL"), {
      target: { value: "https://example.com/careers/123" },
    });
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "Sounds great" } });

    fireEvent.click(screen.getByRole("button", { name: "Add job" }));

    await waitFor(() => expect(client.createManualJobEntry).toHaveBeenCalledTimes(1));
    expect(client.createManualJobEntry).toHaveBeenCalledWith({
      title: "Senior Engineer",
      company: "Acme",
      location: "Remote",
      sourceLabel: null,
      sourceUrl: "https://example.com/careers/123",
      notes: "Sounds great",
    });

    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: applicationTrackerKeys.all }),
    );
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("shows a spinner and disables the submit button while the mutation is pending", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    let resolveMutation: (value: ManualJobEntry) => void = () => {};
    vi.spyOn(client, "createManualJobEntry").mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveMutation = resolve;
        }),
    );

    render(<AddManualJobDialog open={true} onOpenChange={() => {}} />, {
      wrapper: makeWrapper(queryClient),
    });

    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: "Add job" }));

    const submitButton = await screen.findByRole("button", { name: "Adding…" });
    expect(submitButton).toBeDisabled();
    expect(submitButton.querySelector("svg")).toHaveClass("animate-spin");

    resolveMutation(sampleEntry);
    await waitFor(() => expect(screen.getByRole("button", { name: "Add job" })).not.toBeDisabled());
  });

  it("shows a form-level error and keeps the dialog open with input preserved when the request fails", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.spyOn(client, "createManualJobEntry").mockRejectedValue(
      new Error("Failed to create manual job entry: 500"),
    );
    const onOpenChange = vi.fn();

    render(<AddManualJobDialog open={true} onOpenChange={onOpenChange} />, {
      wrapper: makeWrapper(queryClient),
    });

    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: "Add job" }));

    await waitFor(() =>
      expect(screen.getByText("Couldn't add this job. Please try again.")).toBeInTheDocument(),
    );

    // Dialog must not close on failure, and the candidate's typed input must survive.
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
    expect(screen.getByLabelText("Job title")).toHaveValue("Senior Engineer");
    expect(screen.getByLabelText("Company")).toHaveValue("Acme");
  });
});
