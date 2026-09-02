import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StaffGuard } from "./staff-guard";
import * as authProvider from "@/providers/auth-provider";
import LoginPage from "@/app/(auth)/login/page";

const replaceMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  usePathname: () => window.location.pathname,
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

function mockUseAuth(overrides: Partial<ReturnType<typeof authProvider.useAuth>>) {
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
  replaceMock.mockReset();
  pushMock.mockReset();
  window.history.replaceState({}, "", "/osint");
});

describe("StaffGuard", () => {
  it("preserves the local destination for unauthenticated login", () => {
    mockUseAuth({ user: null });
    render(
      <StaffGuard>
        <div>Staff content</div>
      </StaffGuard>,
    );
    expect(replaceMock).toHaveBeenCalledWith("/login?redirect=%2Fosint");
  });

  it("round-trips the OSINT tiers query through StaffGuard and login", async () => {
    window.history.replaceState({}, "", "/osint?tiers=tier1,tier3");
    mockUseAuth({ user: null });
    const guard = render(
      <StaffGuard>
        <div>Staff content</div>
      </StaffGuard>,
    );

    const loginUrl = replaceMock.mock.calls[0]?.[0] as string;
    expect(loginUrl).toBe("/login?redirect=%2Fosint%3Ftiers%3Dtier1%252Ctier3");
    guard.unmount();

    const login = vi.fn().mockResolvedValue({
      is_superuser: false,
      role_id: "role-1",
      role_name: "recruiter",
      permissions: [],
    });
    mockUseAuth({ login });
    window.history.replaceState({}, "", loginUrl);
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "recruiter@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    await waitFor(() => expect(pushMock).toHaveBeenCalled());
    const returnedUrl = pushMock.mock.calls[0]?.[0] as string;
    expect(returnedUrl).toBe("/osint?tiers=tier1%2Ctier3");
    expect(new URL(returnedUrl, "https://hyrepath.local").searchParams.get("tiers")).toBe(
      "tier1,tier3",
    );
  });

  it("sends a candidate to Matches", () => {
    mockUseAuth({
      user: {
        id: "u1",
        email: "candidate@example.com",
        first_name: "Can",
        last_name: "Didate",
        is_verified: true,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        is_superuser: false,
        role_id: null,
        role_name: null,
        permissions: [],
      },
    });
    render(
      <StaffGuard>
        <div>Staff content</div>
      </StaffGuard>,
    );
    expect(replaceMock).toHaveBeenCalledWith("/app/matches");
    expect(screen.queryByText("Staff content")).not.toBeInTheDocument();
  });

  it.each([
    ["assigned-role staff", false, "role-1"],
    ["superuser", true, null],
  ])("renders children for %s", (_name, isSuperuser, roleId) => {
    mockUseAuth({
      user: {
        id: "u1",
        email: "staff@example.com",
        first_name: "Staff",
        last_name: "User",
        is_verified: true,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        is_superuser: isSuperuser,
        role_id: roleId,
        role_name: roleId ? "recruiter" : null,
        permissions: [],
      },
    });
    render(
      <StaffGuard>
        <div>Staff content</div>
      </StaffGuard>,
    );
    expect(screen.getByText("Staff content")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
