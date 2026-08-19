import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AdminGuard } from "./admin-guard";
import * as authProvider from "@/providers/auth-provider";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => "/app/admin/users",
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
});

describe("AdminGuard", () => {
  it("shows a loading spinner while auth is resolving", () => {
    mockUseAuth({ loading: true, user: null });
    const { container } = render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(container.querySelector(".animate-spin")).toBeTruthy();
    expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
  });

  it("redirects to login when there is no user", () => {
    mockUseAuth({ loading: false, user: null });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(pushMock).toHaveBeenCalledWith("/login?redirect=%2Fapp%2Fadmin%2Fusers");
  });

  it("redirects non-admin users to the dashboard", () => {
    mockUseAuth({
      loading: false,
      user: {
        id: "u1",
        email: "user@example.com",
        first_name: "Regular",
        last_name: "User",
        is_verified: true,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        is_superuser: false,
        role_name: null,
      },
    });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(pushMock).toHaveBeenCalledWith("/app/dashboard");
    expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
  });

  it("renders children for a superuser", () => {
    mockUseAuth({
      loading: false,
      user: {
        id: "u1",
        email: "admin@example.com",
        first_name: "Admin",
        last_name: "User",
        is_verified: true,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        is_superuser: true,
        role_name: null,
      },
    });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(screen.getByText("Admin content")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("renders children for a user with a role_name even without is_superuser", () => {
    mockUseAuth({
      loading: false,
      user: {
        id: "u1",
        email: "support@example.com",
        first_name: "Support",
        last_name: "User",
        is_verified: true,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        is_superuser: false,
        role_name: "support",
      },
    });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(screen.getByText("Admin content")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });
});
