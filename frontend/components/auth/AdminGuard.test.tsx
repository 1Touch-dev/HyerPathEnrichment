import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AdminGuard } from "./admin-guard";
import * as authProvider from "@/providers/auth-provider";
import {
  DESK_CANDIDATE_HOME,
  DESK_RECRUITER_HOME,
  hasRolesWrite,
  isOwnerUser,
  isStaffUser,
} from "./desk-guard-contract";

const pushMock = vi.fn();
let pathnameMock = "/desk/users";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => pathnameMock,
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

/** QA-000b fixtures — candidate, recruiter, owner, superuser. */
const candidateUser = {
  id: "u1",
  email: "user@example.com",
  first_name: "Regular",
  last_name: "User",
  is_verified: true,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  is_superuser: false,
  role_name: null,
};

const recruiterUser = {
  id: "u1",
  email: "recruiter@example.com",
  first_name: "Recruiter",
  last_name: "User",
  is_verified: true,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  is_superuser: false,
  role_name: "recruiter",
};

const superuserUser = {
  id: "u1",
  email: "admin@example.com",
  first_name: "Admin",
  last_name: "User",
  is_verified: true,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  is_superuser: true,
  role_name: null,
};

beforeEach(() => {
  vi.restoreAllMocks();
  pushMock.mockReset();
  pathnameMock = "/desk/users";
});

describe("CTR-PERM fail-closed helpers", () => {
  it("does not grant roles:write when permissions are missing", () => {
    expect(hasRolesWrite(undefined)).toBe(false);
    expect(isOwnerUser({ is_superuser: false })).toBe(false);
    expect(isStaffUser(candidateUser)).toBe(false);
  });

  it("accepts string, resource/action, and name permission shapes", () => {
    expect(hasRolesWrite(["roles:write"])).toBe(true);
    expect(hasRolesWrite([{ resource: "roles", action: "write" }])).toBe(true);
    expect(hasRolesWrite([{ name: "roles:write" }])).toBe(true);
    expect(hasRolesWrite([{ resource: "users", action: "read" }])).toBe(false);
  });
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
    expect(pushMock).toHaveBeenCalledWith("/login?redirect=%2Fdesk%2Fusers");
  });

  it("redirects non-staff users to candidate home", () => {
    mockUseAuth({ loading: false, user: candidateUser });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(pushMock).toHaveBeenCalledWith(DESK_CANDIDATE_HOME);
    expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
  });

  it("renders children for a superuser", () => {
    mockUseAuth({ loading: false, user: superuserUser });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(screen.getByText("Admin content")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("renders children for a recruiter on non-owner Desk routes", () => {
    mockUseAuth({ loading: false, user: recruiterUser });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(screen.getByText("Admin content")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("does not treat a recruiter as admin on owner-only routes", () => {
    pathnameMock = "/desk/roles";
    mockUseAuth({ loading: false, user: recruiterUser });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(pushMock).toHaveBeenCalledWith(DESK_RECRUITER_HOME);
    expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
  });

  it("renders children for a superuser on owner-only routes", () => {
    pathnameMock = "/desk/roles";
    mockUseAuth({ loading: false, user: superuserUser });
    render(
      <AdminGuard>
        <div>Admin content</div>
      </AdminGuard>,
    );
    expect(screen.getByText("Admin content")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("renders children for a staff user with roles:write on owner-only routes", () => {
    pathnameMock = "/desk/feature-flags";
    mockUseAuth({
      loading: false,
      user: {
        ...recruiterUser,
        role_name: "team_owner",
        permissions: ["roles:write"],
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
