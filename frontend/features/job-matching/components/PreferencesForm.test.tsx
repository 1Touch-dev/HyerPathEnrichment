import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { PreferencesForm } from "./PreferencesForm";
import * as usePreferencesHooks from "../hooks/usePreferences";
import type { CandidateJobPreferences } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const samplePreferences: CandidateJobPreferences = {
  userId: "u1",
  sourceDocumentId: null,
  desiredRoles: ["Backend Engineer"],
  desiredLocations: ["Remote"],
  remotePreference: "remote",
  salaryMin: 100000,
  salaryMax: 150000,
  salaryCurrency: "USD",
  notificationChannels: ["email"],
  digestFrequency: "daily",
  isScanEnabled: true,
  lastScannedAt: null,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

const mutateMock = vi.fn();

function mockUsePreferences(overrides: Partial<UseQueryResult<CandidateJobPreferences>> = {}) {
  vi.spyOn(usePreferencesHooks, "usePreferences").mockReturnValue({
    data: undefined,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<CandidateJobPreferences>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  mutateMock.mockReset();
  vi.spyOn(usePreferencesHooks, "useUpdatePreferences").mockReturnValue({
    mutate: mutateMock,
    isPending: false,
  } as unknown as ReturnType<typeof usePreferencesHooks.useUpdatePreferences>);
});

describe("PreferencesForm", () => {
  it("renders a loading skeleton while preferences are loading", () => {
    mockUsePreferences({ isLoading: true });
    const { container } = render(<PreferencesForm />, { wrapper });
    expect(container.querySelector(".animate-pulse")).toBeTruthy();
  });

  it("renders the form with empty defaults when there is no data yet", () => {
    mockUsePreferences({ data: undefined, isLoading: false });
    render(<PreferencesForm />, { wrapper });
    expect(screen.getByLabelText("Minimum salary")).toHaveValue(null);
    expect(screen.getByLabelText("Desired roles")).toHaveValue("");
    expect(screen.getByLabelText("Desired locations")).toHaveValue("");
    expect(screen.getByText("Save preferences")).toBeInTheDocument();
  });

  it("submits the form with the expected shape, including the newly-added fields", () => {
    mockUsePreferences({ data: samplePreferences, isLoading: false });
    render(<PreferencesForm />, { wrapper });

    const form = screen.getByText("Save preferences").closest("form");
    expect(form).not.toBeNull();
    form!.requestSubmit();

    expect(mutateMock).toHaveBeenCalledWith({
      desiredRoles: ["Backend Engineer"],
      desiredLocations: ["Remote"],
      salaryMin: 100000,
      salaryMax: 150000,
      remotePreference: "remote",
      notificationChannels: ["email"],
      digestFrequency: "daily",
      isScanEnabled: true,
    });
  });

  it("round-trips edits to desiredRoles/desiredLocations as comma-split arrays", () => {
    mockUsePreferences({ data: samplePreferences, isLoading: false });
    render(<PreferencesForm />, { wrapper });

    const rolesInput = screen.getByLabelText("Desired roles");
    fireEvent.change(rolesInput, { target: { value: "Staff Engineer, Principal Engineer" } });

    const locationsInput = screen.getByLabelText("Desired locations");
    fireEvent.change(locationsInput, { target: { value: "Remote, Austin, TX" } });

    const form = screen.getByText("Save preferences").closest("form");
    form!.requestSubmit();

    expect(mutateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        desiredRoles: ["Staff Engineer", "Principal Engineer"],
        desiredLocations: ["Remote", "Austin", "TX"],
      }),
    );
  });

  it("toggles a notification channel and includes it on submit", () => {
    mockUsePreferences({
      data: { ...samplePreferences, notificationChannels: [] },
      isLoading: false,
    });
    render(<PreferencesForm />, { wrapper });

    const emailCheckbox = screen.getByLabelText("Email");
    fireEvent.click(emailCheckbox);

    const form = screen.getByText("Save preferences").closest("form");
    form!.requestSubmit();

    expect(mutateMock).toHaveBeenCalledWith(
      expect.objectContaining({ notificationChannels: ["email"] }),
    );
  });

  it("submits the selected digest frequency", () => {
    mockUsePreferences({
      data: { ...samplePreferences, digestFrequency: "weekly" },
      isLoading: false,
    });
    render(<PreferencesForm />, { wrapper });

    const form = screen.getByText("Save preferences").closest("form");
    form!.requestSubmit();

    expect(mutateMock).toHaveBeenCalledWith(expect.objectContaining({ digestFrequency: "weekly" }));
  });

  it("renders the SMS notifications switch as disabled and unchecked", () => {
    mockUsePreferences({ data: samplePreferences, isLoading: false });
    render(<PreferencesForm />, { wrapper });

    const smsLabel = screen.getByText("SMS notifications");
    const container = smsLabel.closest("div.flex");
    const smsSwitch = container?.querySelector("button[role='switch']");
    expect(smsSwitch).toBeDisabled();
    expect(smsSwitch).toHaveAttribute("data-state", "unchecked");
  });

  it("renders the Webhook notifications switch as disabled and unchecked", () => {
    mockUsePreferences({ data: samplePreferences, isLoading: false });
    render(<PreferencesForm />, { wrapper });

    const webhookLabel = screen.getByText("Webhook notifications");
    const container = webhookLabel.closest("div.flex");
    const webhookSwitch = container?.querySelector("button[role='switch']");
    expect(webhookSwitch).toBeDisabled();
    expect(webhookSwitch).toHaveAttribute("data-state", "unchecked");
  });
});
