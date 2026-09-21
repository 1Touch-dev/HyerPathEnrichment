import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthGuard } from "./auth-guard";
import * as authProvider from "@/providers/auth-provider";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => window.location.pathname,
}));

function mockUseAuth(overrides: Partial<ReturnType<typeof authProvider.useAuth>> = {}) {
  vi.spyOn(authProvider, "useAuth").mockReturnValue({
    user: null,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
    deleteAccount: vi.fn(),
    refetchUser: vi.fn(),
    ...overrides,
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
  pushMock.mockReset();
  window.history.replaceState({}, "", "/app/dashboard");
});

describe("AuthGuard", () => {
  it("announces account loading as a status", () => {
    mockUseAuth({ loading: true });

    render(
      <AuthGuard>
        <div>Candidate content</div>
      </AuthGuard>,
    );

    expect(screen.getByRole("status", { name: "Loading account" })).toBeInTheDocument();
  });

  it("preserves the Candidate query string in the login redirect", () => {
    window.history.replaceState({}, "", "/app/dashboard?tab=matches&sort=newest");
    mockUseAuth();

    render(
      <AuthGuard>
        <div>Candidate content</div>
      </AuthGuard>,
    );

    expect(pushMock).toHaveBeenCalledWith(
      "/login?redirect=%2Fapp%2Fdashboard%3Ftab%3Dmatches%26sort%3Dnewest",
    );
    expect(screen.getByRole("status", { name: "Redirecting to login" })).toBeInTheDocument();
    expect(screen.queryByText("Candidate content")).not.toBeInTheDocument();
  });
});
