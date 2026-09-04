import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AdminGuard } from "./admin-guard";
import * as authProvider from "@/providers/auth-provider";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
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
  replaceMock.mockReset();
  window.history.replaceState({}, "", "/desk/roles");
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
    expect(screen.getByRole("status", { name: "Loading account" })).toBeInTheDocument();
    expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
  });

  it("redirects to login when there is no user", () => {
    mockUseAuth({ loading: false, user: null });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(replaceMock).toHaveBeenCalledWith("/login?redirect=%2Fdesk%2Froles");
  });

  it("preserves the query string when redirecting to login", () => {
    window.history.replaceState({}, "", "/desk/roles?tab=permissions&role=owner");
    mockUseAuth({ loading: false, user: null });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(replaceMock).toHaveBeenCalledWith(
      "/login?redirect=%2Fdesk%2Froles%3Ftab%3Dpermissions%26role%3Downer",
    );
  });

  it("redirects candidates to their Candidate home", () => {
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
        role_id: null,
        role_name: null,
        permissions: [],
      },
    });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(replaceMock).toHaveBeenCalledWith("/app/matches");
    expect(
      screen.getByRole("status", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
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
        role_id: null,
        role_name: null,
        permissions: [],
      },
    });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(screen.getByText("Admin content")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("redirects a recruiter to the recruiter Desk home", () => {
    mockUseAuth({
      loading: false,
      user: {
        id: "u1",
        email: "recruiter@example.com",
        first_name: "Recruiter",
        last_name: "User",
        is_verified: true,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        is_superuser: false,
        role_id: "role-1",
        role_name: "recruiter",
        permissions: [{ resource: "linkedin_sourcing", action: "write" }],
      },
    });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
    expect(replaceMock).toHaveBeenCalledWith("/desk/sourcing-leads");
    expect(
      screen.getByRole("status", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
  });

  it("does not grant desk-home access from an unrelated granular permission", () => {
    mockUseAuth({
      loading: false,
      user: {
        id: "u1",
        email: "recruiter@example.com",
        first_name: "Recruiter",
        last_name: "User",
        is_verified: true,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        is_superuser: false,
        role_id: "role-1",
        role_name: "recruiter",
        permissions: [{ resource: "roles", action: "read" }],
      },
    });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
    expect(replaceMock).toHaveBeenCalledWith("/desk/roles");
    expect(
      screen.getByRole("status", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
  });

  it("grants permission-gated access from an exact permission pair", () => {
    mockUseAuth({
      loading: false,
      user: {
        id: "u1",
        email: "recruiter@example.com",
        first_name: "Recruiter",
        last_name: "User",
        is_verified: true,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        is_superuser: false,
        role_id: "role-1",
        role_name: "recruiter",
        permissions: [{ resource: "users", action: "read" }],
      },
    });
    render(
      <AdminGuard permission={{ resource: "users", action: "read" }}>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(screen.getByText("Admin content")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("renders desk-home children for a system health reader", () => {
    mockUseAuth({
      loading: false,
      user: {
        id: "u1",
        email: "ops@example.com",
        first_name: "Ops",
        last_name: "Reader",
        is_verified: true,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        is_superuser: false,
        role_id: "role-2",
        role_name: "admin",
        permissions: [{ resource: "system_health", action: "read" }],
      },
    });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(screen.getByText("Admin content")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("denies role-only staff without the desk-home permission", () => {
    mockUseAuth({
      loading: false,
      user: {
        id: "u1",
        email: "owner@example.com",
        first_name: "Team",
        last_name: "Owner",
        is_verified: true,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        is_superuser: false,
        role_id: "role-2",
        role_name: "team_owner",
        permissions: [],
      },
    });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
    expect(replaceMock).toHaveBeenCalledWith("/osint");
  });
});
