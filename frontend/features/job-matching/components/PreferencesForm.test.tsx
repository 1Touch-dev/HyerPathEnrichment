import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { PreferencesForm } from "./PreferencesForm";
import * as usePreferencesHooks from "../hooks/usePreferences";
import * as usePushSubscriptionHooks from "../hooks/usePushSubscription";
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
  webhookUrl: null,
  digestFrequency: "daily",
  isScanEnabled: true,
  lastScannedAt: null,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

const mutateMock = vi.fn();
const pushSubscribeMock = vi.fn();
const pushUnsubscribeMock = vi.fn();

function mockUsePreferences(overrides: Partial<UseQueryResult<CandidateJobPreferences>> = {}) {
  vi.spyOn(usePreferencesHooks, "usePreferences").mockReturnValue({
    data: undefined,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<CandidateJobPreferences>);
}

function mockUsePushSubscription(
  overrides: Partial<ReturnType<typeof usePushSubscriptionHooks.usePushSubscription>> = {},
) {
  vi.spyOn(usePushSubscriptionHooks, "usePushSubscription").mockReturnValue({
    isSupported: true,
    isSubscribed: false,
    subscribe: pushSubscribeMock,
    unsubscribe: pushUnsubscribeMock,
    error: null,
    ...overrides,
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
  mutateMock.mockReset();
  pushSubscribeMock.mockReset().mockResolvedValue(undefined);
  pushUnsubscribeMock.mockReset().mockResolvedValue(undefined);
  vi.spyOn(usePreferencesHooks, "useUpdatePreferences").mockReturnValue({
    mutate: mutateMock,
    isPending: false,
  } as unknown as ReturnType<typeof usePreferencesHooks.useUpdatePreferences>);
  mockUsePushSubscription();
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
      webhookUrl: null,
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

  it("renders an enabled webhook checkbox and reveals a URL input once checked", () => {
    mockUsePreferences({
      data: { ...samplePreferences, notificationChannels: [] },
      isLoading: false,
    });
    render(<PreferencesForm />, { wrapper });

    expect(screen.queryByLabelText("Webhook URL")).not.toBeInTheDocument();

    const webhookCheckbox = screen.getByLabelText("Webhook");
    fireEvent.click(webhookCheckbox);

    expect(screen.getByLabelText("Webhook URL")).toBeInTheDocument();

    const form = screen.getByText("Save preferences").closest("form");
    form!.requestSubmit();

    expect(mutateMock).toHaveBeenCalledWith(
      expect.objectContaining({ notificationChannels: ["webhook"] }),
    );
  });

  it("submits the webhook URL when the webhook channel is enabled", () => {
    mockUsePreferences({
      data: { ...samplePreferences, notificationChannels: ["webhook"], webhookUrl: null },
      isLoading: false,
    });
    render(<PreferencesForm />, { wrapper });

    const webhookUrlInput = screen.getByLabelText("Webhook URL");
    fireEvent.change(webhookUrlInput, { target: { value: "https://example.com/hook" } });

    const form = screen.getByText("Save preferences").closest("form");
    form!.requestSubmit();

    expect(mutateMock).toHaveBeenCalledWith(
      expect.objectContaining({ webhookUrl: "https://example.com/hook" }),
    );
  });

  it("renders an enabled push checkbox when push is supported", () => {
    mockUsePreferences({ data: samplePreferences, isLoading: false });
    render(<PreferencesForm />, { wrapper });

    const pushCheckbox = screen.getByLabelText("Push");
    expect(pushCheckbox).not.toBeDisabled();
  });

  it("renders the push option as disabled when the browser is unsupported", () => {
    mockUsePreferences({ data: samplePreferences, isLoading: false });
    mockUsePushSubscription({ isSupported: false });
    render(<PreferencesForm />, { wrapper });

    const pushLabel = screen.getByText("Push notifications");
    const container = pushLabel.closest("div.flex");
    const pushSwitch = container?.querySelector("button[role='switch']");
    expect(pushSwitch).toBeDisabled();
    expect(screen.getByText("Not supported in this browser.")).toBeInTheDocument();
  });

  it("subscribes and checks the push box on success, including it on submit", async () => {
    mockUsePreferences({
      data: { ...samplePreferences, notificationChannels: [] },
      isLoading: false,
    });
    render(<PreferencesForm />, { wrapper });

    const pushCheckbox = screen.getByLabelText("Push");
    fireEvent.click(pushCheckbox);

    await waitFor(() => expect(pushSubscribeMock).toHaveBeenCalled());
    await waitFor(() => expect(pushCheckbox).toHaveAttribute("data-state", "checked"));

    const form = screen.getByText("Save preferences").closest("form");
    form!.requestSubmit();

    expect(mutateMock).toHaveBeenCalledWith(
      expect.objectContaining({ notificationChannels: ["push"] }),
    );
  });

  it("shows an inline error and leaves the push box unchecked when subscribe fails", async () => {
    pushSubscribeMock.mockRejectedValue(new Error("Notification permission was denied."));
    mockUsePreferences({
      data: { ...samplePreferences, notificationChannels: [] },
      isLoading: false,
    });
    render(<PreferencesForm />, { wrapper });

    const pushCheckbox = screen.getByLabelText("Push");
    fireEvent.click(pushCheckbox);

    await waitFor(() =>
      expect(screen.getByText("Notification permission was denied.")).toBeInTheDocument(),
    );
    expect(pushCheckbox).toHaveAttribute("data-state", "unchecked");

    const form = screen.getByText("Save preferences").closest("form");
    form!.requestSubmit();

    expect(mutateMock).toHaveBeenCalledWith(expect.objectContaining({ notificationChannels: [] }));
  });
});
