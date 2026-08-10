import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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
  desiredRoles: [],
  desiredLocations: [],
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
    expect(screen.getByText("Save preferences")).toBeInTheDocument();
  });

  it("submits the form with the expected shape", () => {
    mockUsePreferences({ data: samplePreferences, isLoading: false });
    render(<PreferencesForm />, { wrapper });

    const form = screen.getByText("Save preferences").closest("form");
    expect(form).not.toBeNull();
    form!.requestSubmit();

    expect(mutateMock).toHaveBeenCalledWith({
      salaryMin: 100000,
      salaryMax: 150000,
      remotePreference: "remote",
      isScanEnabled: true,
    });
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
});
