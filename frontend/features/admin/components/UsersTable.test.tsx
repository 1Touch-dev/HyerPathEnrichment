import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { UsersTable } from "./UsersTable";
import * as useAdminUsersHooks from "../hooks/useAdminUsers";
import * as client from "../api/client";
import * as authProvider from "@/providers/auth-provider";
import type { AdminUser, AdminUserListResponse } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/desk/users",
}));

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const baseUser: AdminUser = {
  id: "u1",
  email: "jane@example.com",
  firstName: "Jane",
  lastName: "Doe",
  isActive: true,
  isVerified: true,
  isSuperuser: false,
  roleId: null,
  roleName: null,
  mfaEnabled: false,
  createdAt: "2026-01-01T00:00:00Z",
  deletedAt: null,
};

const sampleList: AdminUserListResponse = {
  items: [baseUser],
  nextCursor: null,
  hasMore: false,
};

function mockUseAdminUsers(overrides: Partial<UseQueryResult<AdminUserListResponse>> = {}) {
  vi.spyOn(useAdminUsersHooks, "useAdminUsers").mockReturnValue({
    data: sampleList,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<AdminUserListResponse>);
}

const updateStatusMutate = vi.fn();
const assignRoleMutate = vi.fn();

function mockMutations() {
  vi.spyOn(useAdminUsersHooks, "useUpdateUserStatus").mockReturnValue({
    mutate: updateStatusMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useAdminUsersHooks.useUpdateUserStatus>);
  vi.spyOn(useAdminUsersHooks, "useAssignUserRole").mockReturnValue({
    mutate: assignRoleMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useAdminUsersHooks.useAssignUserRole>);
}

function mockUseAuth(overrides: Partial<ReturnType<typeof authProvider.useAuth>> = {}) {
  vi.spyOn(authProvider, "useAuth").mockReturnValue({
    user: {
      id: "admin1",
      email: "admin@example.com",
      first_name: "Admin",
      last_name: "User",
      is_verified: true,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      is_superuser: true,
      role_name: null,
    },
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
  updateStatusMutate.mockReset();
  assignRoleMutate.mockReset();
  vi.spyOn(client, "fetchRoles").mockResolvedValue([]);
  mockUseAdminUsers();
  mockMutations();
  mockUseAuth();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("UsersTable", () => {
  it("renders a row per user with email, status, and MFA badges", () => {
    render(<UsersTable />, { wrapper });
    expect(screen.getByText("jane@example.com")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Off")).toBeInTheDocument();
  });

  it("renders an empty state when there are no users", () => {
    mockUseAdminUsers({ data: { items: [], nextCursor: null, hasMore: false } });
    render(<UsersTable />, { wrapper });
    expect(screen.getByText("No users found")).toBeInTheDocument();
  });

  it("calls useUpdateUserStatus when Suspend is clicked, after confirmation", () => {
    render(<UsersTable />, { wrapper });
    fireEvent.click(screen.getByText("Suspend"));
    expect(updateStatusMutate).toHaveBeenCalledWith({ userId: "u1", isActive: false });
  });

  it("does not call useUpdateUserStatus when the confirmation is declined", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<UsersTable />, { wrapper });
    fireEvent.click(screen.getByText("Suspend"));
    expect(updateStatusMutate).not.toHaveBeenCalled();
  });

  it("shows the Assign role action only for superusers", () => {
    render(<UsersTable />, { wrapper });
    expect(screen.getByText("Assign role")).toBeInTheDocument();
  });

  it("hides the Assign role action for non-superusers", () => {
    mockUseAuth({
      user: {
        id: "admin2",
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
    render(<UsersTable />, { wrapper });
    expect(screen.queryByText("Assign role")).not.toBeInTheDocument();
  });

  it("shows the Log in as action for admins and superusers, gated on impersonation:start", () => {
    render(<UsersTable />, { wrapper });
    expect(screen.getByText("Log in as")).toBeInTheDocument();
  });

  it("hides the Log in as action for support-role users", () => {
    mockUseAuth({
      user: {
        id: "admin2",
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
    render(<UsersTable />, { wrapper });
    expect(screen.queryByText("Log in as")).not.toBeInTheDocument();
  });

  it("disables the Next page button when hasMore is false", () => {
    render(<UsersTable />, { wrapper });
    expect(screen.getByText("Next page")).toBeDisabled();
  });

  it("enables the Next page button when hasMore is true", () => {
    mockUseAdminUsers({ data: { items: [baseUser], nextCursor: "cursor2", hasMore: true } });
    render(<UsersTable />, { wrapper });
    expect(screen.getByText("Next page")).not.toBeDisabled();
  });

  it("opens the impersonation dialog when Log in as is clicked", async () => {
    render(<UsersTable />, { wrapper });
    fireEvent.click(screen.getByText("Log in as"));
    await waitFor(() => expect(screen.getByText("Log in as jane@example.com")).toBeInTheDocument());
  });
});
