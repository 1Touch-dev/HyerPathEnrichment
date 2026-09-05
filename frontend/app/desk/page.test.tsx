import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth, type User } from "@/providers/auth-provider";
import DeskIndexPage from "./page";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock("@/providers/auth-provider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/features/admin", () => ({
  SystemHealthPanel: () => <div>Owner system health</div>,
}));

function staffUser(roleName: string | null, isSuperuser = false): User {
  return {
    id: "user-1",
    email: "staff@example.com",
    first_name: "Staff",
    last_name: "User",
    is_verified: true,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    is_superuser: isSuperuser,
    role_id: isSuperuser ? null : "role-1",
    role_name: roleName,
    permissions: [],
  };
}

function mockUser(user: User) {
  vi.mocked(useAuth).mockReturnValue({
    user,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
    deleteAccount: vi.fn(),
    refetchUser: vi.fn(),
  });
}

beforeEach(() => {
  replaceMock.mockReset();
});

describe("DeskIndexPage", () => {
  it("renders desk-home content for a superuser", () => {
    mockUser(staffUser(null, true));
    render(<DeskIndexPage />);

    expect(screen.getByText("Owner system health")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("renders desk-home content for a non-superuser with system_health:read", () => {
    mockUser({
      ...staffUser("admin"),
      permissions: [{ resource: "system_health", action: "read" }],
    });
    render(<DeskIndexPage />);

    expect(screen.getByText("Owner system health")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it.each([
    [
      "recruiter",
      { role_id: "role-1", permissions: [{ resource: "linkedin_sourcing", action: "write" }] },
      "/desk/sourcing-leads",
    ],
    [
      "support",
      { role_id: "role-1", permissions: [{ resource: "users", action: "read" }] },
      "/desk/users",
    ],
    ["team_owner without permissions", { role_id: "role-1", permissions: [] }, "/osint"],
    ["content_moderator", { role_id: "role-1", permissions: [] }, "/osint"],
  ])("redirects %s staff to their allowed home", (roleName, overrides, destination) => {
    mockUser({
      ...staffUser(roleName),
      ...overrides,
    });
    render(<DeskIndexPage />);

    expect(screen.queryByText("Owner system health")).not.toBeInTheDocument();
    expect(
      screen.getByRole("status", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
    expect(replaceMock).toHaveBeenCalledWith(destination);
  });
});
