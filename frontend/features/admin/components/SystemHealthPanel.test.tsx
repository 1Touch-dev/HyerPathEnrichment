import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { SystemHealthPanel } from "./SystemHealthPanel";
import * as useSystemHealthHooks from "../hooks/useSystemHealth";
import type { SystemHealthSnapshot } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const baseSnapshot: SystemHealthSnapshot = {
  databaseOk: true,
  databaseLatencyMs: 5,
  redisOk: true,
  redisLatencyMs: 2,
  prometheusConfigured: false,
  signals: {},
};

function mockUseSystemHealth(overrides: Partial<UseQueryResult<SystemHealthSnapshot>> = {}) {
  vi.spyOn(useSystemHealthHooks, "useSystemHealth").mockReturnValue({
    data: baseSnapshot,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<SystemHealthSnapshot>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  mockUseSystemHealth();
});

describe("SystemHealthPanel", () => {
  it("renders a loading message while health data is loading", () => {
    mockUseSystemHealth({ data: undefined, isLoading: true });
    render(<SystemHealthPanel />, { wrapper });
    expect(screen.getByText("Loading system health…")).toBeInTheDocument();
  });

  it("renders the self-checks section with database and redis latency", () => {
    render(<SystemHealthPanel />, { wrapper });
    expect(screen.getByText("Self-checks")).toBeInTheDocument();
    expect(screen.getByText("Database")).toBeInTheDocument();
    expect(screen.getByText("5 ms")).toBeInTheDocument();
    expect(screen.getByText("Redis")).toBeInTheDocument();
    expect(screen.getByText("2 ms")).toBeInTheDocument();
  });

  it("shows a Down badge when a self-check fails", () => {
    mockUseSystemHealth({ data: { ...baseSnapshot, databaseOk: false } });
    render(<SystemHealthPanel />, { wrapper });
    expect(screen.getByText("Down")).toBeInTheDocument();
  });

  it("shows the fail-soft empty state when prometheus is not configured", () => {
    render(<SystemHealthPanel />, { wrapper });
    expect(screen.getByText("Golden signals not configured")).toBeInTheDocument();
    expect(
      screen.getByText("Set PROMETHEUS_QUERY_URL to enable the golden-signals panel."),
    ).toBeInTheDocument();
  });

  it("renders golden signal cards when prometheus is configured", () => {
    mockUseSystemHealth({
      data: {
        ...baseSnapshot,
        prometheusConfigured: true,
        signals: { latency: 120, traffic: 42, errors: 0, saturation: null },
      },
    });
    render(<SystemHealthPanel />, { wrapper });
    expect(screen.getByText("Latency")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("Traffic")).toBeInTheDocument();
    expect(screen.getByText("Saturation")).toBeInTheDocument();
    expect(screen.queryByText("Golden signals not configured")).not.toBeInTheDocument();
  });
});
