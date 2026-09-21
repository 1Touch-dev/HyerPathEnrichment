import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
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

function mockUseFeatureFlags(overrides: Partial<UseQueryResult<FeatureFlag[]>> = {}) {
  vi.spyOn(useFeatureFlagsHooks, "useFeatureFlags").mockReturnValue({
    data: sampleFlags,
    isLoading: false,
    isError: false,
    ...overrides,
  } as UseQueryResult<FeatureFlag[]>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  mockUseFeatureFlags();
});

describe("FeatureFlagsPanel", () => {
  it("explains that the surface is administration-only and mutations are unavailable", () => {
    render(<FeatureFlagsPanel />, { wrapper });

    expect(screen.getByRole("status")).toHaveTextContent("Administration status only");
    expect(screen.getByRole("status")).toHaveTextContent(
      "No application service consumes these records",
    );
    expect(screen.getByText(/mutation is disabled until a consumer exists/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create flag" })).toBeDisabled();
  });

  it("renders stored values as disabled switches", () => {
    render(<FeatureFlagsPanel />, { wrapper });

    expect(screen.getByText("new_matching_algorithm")).toBeInTheDocument();
    expect(screen.getByText("Enables the new scoring model.")).toBeInTheDocument();
    expect(screen.getByText("updated by admin@example.com")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Toggle new_matching_algorithm" })).toBeDisabled();
    expect(screen.getByRole("switch", { name: "Toggle new_matching_algorithm" })).toBeChecked();
  });

  it("renders a read-only empty state when there are no stored records", () => {
    mockUseFeatureFlags({ data: [] });
    render(<FeatureFlagsPanel />, { wrapper });

    const emptyState = screen.getByRole("status", { name: "No stored feature flag records" });
    expect(emptyState).toHaveAccessibleDescription(
      "Creation remains unavailable while feature flags have no application consumer.",
    );
    expect(emptyState).toHaveTextContent("No stored feature flag records");
  });

  it("announces loading without exposing mutation controls", () => {
    mockUseFeatureFlags({ data: undefined, isLoading: true });
    render(<FeatureFlagsPanel />, { wrapper });

    expect(screen.getByText("Loading feature flag records…")).toHaveAttribute("role", "status");
    expect(screen.getByRole("button", { name: "Create flag" })).toBeDisabled();
  });

  it("shows an unavailable state when stored records fail to load", () => {
    mockUseFeatureFlags({ data: undefined, isError: true });
    render(<FeatureFlagsPanel />, { wrapper });

    const errorState = screen.getByRole("alert", { name: "Feature flag records unavailable" });
    expect(errorState).toHaveAccessibleDescription(
      "The stored administration records could not be loaded.",
    );
    expect(errorState).toHaveTextContent("Feature flag records unavailable");
  });
});
