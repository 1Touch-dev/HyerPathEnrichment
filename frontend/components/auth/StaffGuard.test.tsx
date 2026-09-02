import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StaffGuard } from "./staff-guard";
import * as authProvider from "@/providers/auth-provider";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => "/osint",
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
