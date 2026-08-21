import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { FeatureFlagsPanel } from "./FeatureFlagsPanel";
import * as useFeatureFlagsHooks from "../hooks/useFeatureFlags";
import type { FeatureFlag } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleFlags: FeatureFlag[] = [
  {
    key: "new_matching_algorithm",
    enabled: true,
    value: null,
    description: "Enables the new scoring model.",
    updatedBy: "admin@example.com",
    updatedAt: "2026-01-01T00:00:00Z",
  },
];

const upsertMutate = vi.fn();
const upsertMutateAsync = vi.fn();

function mockUseFeatureFlags(overrides: Partial<UseQueryResult<FeatureFlag[]>> = {}) {
  vi.spyOn(useFeatureFlagsHooks, "useFeatureFlags").mockReturnValue({
    data: sampleFlags,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<FeatureFlag[]>);
}

type UpsertFlagResult = ReturnType<typeof useFeatureFlagsHooks.useUpsertFeatureFlag>;

function mockUpsertFlag(overrides: Partial<UpsertFlagResult> = {}) {
  vi.spyOn(useFeatureFlagsHooks, "useUpsertFeatureFlag").mockReturnValue({
    mutate: upsertMutate,
    mutateAsync: upsertMutateAsync,
    isPending: false,
    ...overrides,
  } as unknown as UpsertFlagResult);
}

beforeEach(() => {
  vi.restoreAllMocks();
  upsertMutate.mockReset();
  upsertMutateAsync.mockReset().mockResolvedValue(undefined);
  mockUseFeatureFlags();
  mockUpsertFlag();
});

describe("FeatureFlagsPanel", () => {
  it("renders a switch row per flag with key and description", () => {
    render(<FeatureFlagsPanel />, { wrapper });
    expect(screen.getByText("new_matching_algorithm")).toBeInTheDocument();
    expect(screen.getByText("Enables the new scoring model.")).toBeInTheDocument();
    expect(screen.getByText("updated by admin@example.com")).toBeInTheDocument();
  });

  it("renders an empty state when there are no flags", () => {
    mockUseFeatureFlags({ data: [] });
    render(<FeatureFlagsPanel />, { wrapper });
    expect(screen.getByText("No feature flags yet")).toBeInTheDocument();
  });

  it("toggles a switch and calls useUpsertFeatureFlag optimistically", () => {
    render(<FeatureFlagsPanel />, { wrapper });
    const switchEl = screen.getByLabelText("Toggle new_matching_algorithm");
    fireEvent.click(switchEl);
    expect(upsertMutate).toHaveBeenCalledWith({
      key: "new_matching_algorithm",
      payload: { enabled: false },
    });
  });

  it("opens the create flag dialog and submits a new key/description", async () => {
    render(<FeatureFlagsPanel />, { wrapper });
    fireEvent.click(screen.getByText("Create flag"));

    const keyInput = screen.getByLabelText("Key");
    fireEvent.change(keyInput, { target: { value: "beta_feature" } });
    const descriptionInput = screen.getByLabelText("Description");
    fireEvent.change(descriptionInput, { target: { value: "A beta feature." } });

    const form = screen.getByLabelText("Key").closest("form");
    expect(form).not.toBeNull();
    form!.requestSubmit();

    await waitFor(() =>
      expect(upsertMutateAsync).toHaveBeenCalledWith({
        key: "beta_feature",
        payload: { enabled: false, description: "A beta feature." },
      }),
    );
  });

  it("shows a validation error when submitting the create dialog without a key", () => {
    render(<FeatureFlagsPanel />, { wrapper });
    fireEvent.click(screen.getByText("Create flag"));

    const form = screen.getByLabelText("Key").closest("form");
    expect(form).not.toBeNull();
    // fireEvent.submit bypasses jsdom's native `required` constraint validation,
    // exercising the component's own guard clause directly.
    fireEvent.submit(form!);

    expect(screen.getByText("Key is required.")).toBeInTheDocument();
    expect(upsertMutateAsync).not.toHaveBeenCalled();
  });
});
