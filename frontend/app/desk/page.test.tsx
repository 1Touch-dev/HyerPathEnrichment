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
  it.each([
    ["admin", false],
    ["team_owner", false],
    [null, true],
  ])("renders owner content for %s", (roleName, isSuperuser) => {
    mockUser(staffUser(roleName, isSuperuser));
    render(<DeskIndexPage />);

    expect(screen.getByText("Owner system health")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it.each([
    ["recruiter", "/desk/sourcing-leads"],
    ["support", "/desk/users"],
    ["content_moderator", "/osint"],
  ])("redirects %s staff to their role home", (roleName, destination) => {
    mockUser(staffUser(roleName));
    render(<DeskIndexPage />);

    expect(screen.queryByText("Owner system health")).not.toBeInTheDocument();
    expect(replaceMock).toHaveBeenCalledWith(destination);
  });
});
