import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth, type User } from "@/providers/auth-provider";
import type { Permission } from "@/src/lib/product-doors";
import type { AdminBrand } from "@/src/lib/types";
import AdminBrandsPage from "./page";

vi.mock("@/providers/auth-provider", () => ({
  useAuth: vi.fn(),
}));

const sampleBrand: AdminBrand = {
  id: "brand-1",
  name: "Acme Staffing",
  slug: "acme-staffing",
  customDomain: null,
  chatbotConfig: null,
  landingPageTierConfig: null,
  isActive: true,
  createdAt: "2026-01-01T00:00:00.000Z",
};

function staffUser(permissions: Permission[], roleName = "recruiter"): User {
  return {
    id: "user-1",
    email: "recruiter@example.com",
    first_name: "Rec",
    last_name: "Ruiter",
    is_verified: true,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    is_superuser: false,
    role_id: "role-recruiter",
    role_name: roleName,
    permissions,
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

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: [sampleBrand] }),
    }),
  );
});

describe("AdminBrandsPage permission gates", () => {
  it("hides write/delete controls for recruiter with brands:read only", async () => {
    mockUser(staffUser([{ resource: "brands", action: "read" }]));
    render(<AdminBrandsPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Acme Staffing")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: "Create brand" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Deactivate" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reactivate" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View landing page" })).toBeInTheDocument();
  });

  it("shows create/edit for brands:write and deactivate for brands:delete", async () => {
    mockUser(
      staffUser([
        { resource: "brands", action: "read" },
        { resource: "brands", action: "write" },
        { resource: "brands", action: "delete" },
      ]),
    );
    render(<AdminBrandsPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Acme Staffing")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Create brand" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Deactivate" })).toBeInTheDocument();
  });

  it("does not show write/delete controls for role-only owner without explicit brand permissions", async () => {
    mockUser(staffUser([], "admin"));
    render(<AdminBrandsPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Acme Staffing")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: "Create brand" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Deactivate" })).not.toBeInTheDocument();
  });
});
