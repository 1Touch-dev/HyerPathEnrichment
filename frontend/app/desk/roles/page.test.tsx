import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminRolesPage from "./page";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleRole = {
  id: "role-custom",
  name: "custom_role",
  description: "Custom",
  is_system: false,
  isSystem: false,
  permissions: [
    {
      id: "perm-1",
      resource: "users",
      action: "read",
      description: null,
    },
  ],
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("AdminRolesPage", () => {
  it("shows an error EmptyState when the roles fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ success: false, error: "Forbidden" }),
      }),
    );

    render(<AdminRolesPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByRole("alert", { name: "Could not load roles" })).toBeInTheDocument();
    });
    expect(screen.getByText(/Access failed or permissions are missing/i)).toBeInTheDocument();
    expect(screen.queryByText("No roles configured")).not.toBeInTheDocument();
  });

  it("shows the empty success state only when the API returns an empty list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: [] }),
      }),
    );

    render(<AdminRolesPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("No roles configured")).toBeInTheDocument();
    });
    expect(screen.queryByRole("alert", { name: "Could not load roles" })).not.toBeInTheDocument();
  });

  it("shows a read-only notice while role mutations are unavailable", async () => {
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/admin/roles" && (!init || !init.method || init.method === "GET")) {
        return {
          ok: true,
          json: async () => ({ success: true, data: [sampleRole] }),
        };
      }
      if (url.includes("/permissions/") && init?.method === "DELETE") {
        return { ok: true, json: async () => ({ success: true }) };
      }
      return { ok: true, json: async () => ({ success: true, data: [] }) };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AdminRolesPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("custom_role")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/temporarily unavailable until ADR21 typed confirmation and step-up/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("Create role")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove users:read/i })).not.toBeInTheDocument();
    expect(screen.queryByText("Add")).not.toBeInTheDocument();
  });
});
