import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DashboardView } from "@/features/dashboard";
import { AppShellAccessProvider, type CandidateMutationAccess } from "./app-shell-access";

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({}),
}));

vi.mock("@/features/enrich", () => ({
  evictStaleJobDetails: vi.fn(),
}));

vi.mock("@/features/history", () => ({
  useJobMetricsQuery: () => ({
    data: {
      total: 0,
      successRate: 0,
      running: 0,
      recent: [],
    },
    isLoading: false,
    error: null,
  }),
}));

describe("Candidate shell impersonation access", () => {
  it.each(["checking", "unavailable", "impersonating"] as CandidateMutationAccess[])(
    "hides cross-product and privileged actions when access is %s",
    (candidateMutationAccess) => {
      render(
        <AppShellAccessProvider candidateMutationAccess={candidateMutationAccess}>
          <DashboardView />
        </AppShellAccessProvider>,
      );

      expect(screen.queryByRole("link", { name: "New enrichment" })).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "System health" })).not.toBeInTheDocument();
      expect(screen.getByRole("link", { name: "View all" })).toHaveAttribute("href", "/app/jobs");
    },
  );

  it("keeps standard Candidate actions outside impersonation", () => {
    render(
      <AppShellAccessProvider candidateMutationAccess="allowed">
        <DashboardView />
      </AppShellAccessProvider>,
    );

    expect(screen.getByRole("link", { name: "New enrichment" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "System health" })).toBeInTheDocument();
  });
});
