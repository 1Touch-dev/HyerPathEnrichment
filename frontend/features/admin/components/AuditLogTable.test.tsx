import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AuditLogTable } from "./AuditLogTable";
import * as useAuditLogsHooks from "../hooks/useAuditLogs";
import * as client from "../api/client";
import type { AdminAuditLogListResponse, AdminUserListResponse } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleLogs: AdminAuditLogListResponse = {
  items: [
    {
      id: "log1",
      actorUserId: "u1",
      impersonatedBy: null,
      action: "user.status_changed",
      targetType: "user",
      targetId: "u2",
      before: null,
      after: null,
      ipAddress: null,
      capturedBy: "explicit",
      createdAt: "2026-01-01T00:00:00Z",
    },
  ],
  nextCursor: null,
  hasMore: false,
};

const sampleUsers: AdminUserListResponse = {
  items: [
    {
      id: "u1",
      email: "actor@example.com",
      firstName: "Actor",
      lastName: "User",
      isActive: true,
      isVerified: true,
      isSuperuser: false,
      roleId: null,
      roleName: null,
      mfaEnabled: false,
      createdAt: "2026-01-01T00:00:00Z",
      deletedAt: null,
    },
  ],
  nextCursor: null,
  hasMore: false,
};

function mockUseAuditLogs(overrides: Partial<UseQueryResult<AdminAuditLogListResponse>> = {}) {
  vi.spyOn(useAuditLogsHooks, "useAuditLogs").mockReturnValue({
    data: sampleLogs,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<AdminAuditLogListResponse>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(client, "fetchAdminUsers").mockResolvedValue(sampleUsers);
  mockUseAuditLogs();
});

describe("AuditLogTable", () => {
  it("renders a row per audit log entry with resolved actor email", async () => {
    render(<AuditLogTable />, { wrapper });
    expect(screen.getByText("user.status_changed")).toBeInTheDocument();
    expect(await screen.findByText("actor@example.com")).toBeInTheDocument();
  });

  it("falls back to the raw actor UUID when it cannot resolve an email", () => {
    vi.spyOn(client, "fetchAdminUsers").mockResolvedValue({
      items: [],
      nextCursor: null,
      hasMore: false,
    });
    render(<AuditLogTable />, { wrapper });
    expect(screen.getByText("u1")).toBeInTheDocument();
  });

  it("shows the captured_by badge distinguishing explicit vs fallback entries", () => {
    render(<AuditLogTable />, { wrapper });
    expect(screen.getByText("explicit")).toBeInTheDocument();
  });

  it("renders an empty state when there are no entries", () => {
    mockUseAuditLogs({ data: { items: [], nextCursor: null, hasMore: false } });
    render(<AuditLogTable />, { wrapper });
    expect(screen.getByText("No audit log entries")).toBeInTheDocument();
  });

  it("filters entries client-side by targetId when provided, and hides the action filter/pagination", () => {
    render(<AuditLogTable targetId="u2" />, { wrapper });
    expect(screen.getByText("user.status_changed")).toBeInTheDocument();
    expect(screen.queryByText("Next page")).not.toBeInTheDocument();
  });

  it("hides entries that do not match the targetId filter", () => {
    render(<AuditLogTable targetId="does-not-exist" />, { wrapper });
    expect(screen.getByText("No audit log entries")).toBeInTheDocument();
  });

  it("disables Next page when hasMore is false", () => {
    render(<AuditLogTable />, { wrapper });
    expect(screen.getByText("Next page")).toBeDisabled();
  });
});
