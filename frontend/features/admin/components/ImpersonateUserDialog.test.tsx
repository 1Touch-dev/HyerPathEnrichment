import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "@/providers/auth-provider";
import type { AdminUser } from "@/src/lib/types";
import { useStartImpersonation } from "../hooks/useImpersonation";
import { ImpersonateUserDialog } from "./ImpersonateUserDialog";

vi.mock("@/providers/auth-provider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../hooks/useImpersonation", () => ({
  useStartImpersonation: vi.fn(),
}));

const mutateAsyncMock = vi.fn();
const assignMock = vi.fn();
const originalLocation = window.location;

Object.defineProperty(window, "location", {
  configurable: true,
  value: { ...originalLocation, assign: assignMock },
});

afterAll(() => {
  Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
});

const targetUser: AdminUser = {
  id: "candidate-1",
  email: "candidate@example.com",
  firstName: "Candidate",
  lastName: "User",
  isActive: true,
  isVerified: true,
  isSuperuser: false,
  roleId: null,
  roleName: null,
  mfaEnabled: false,
  createdAt: "2026-01-01T00:00:00Z",
  deletedAt: null,
};

beforeEach(() => {
  mutateAsyncMock.mockReset().mockResolvedValue(undefined);
  assignMock.mockReset();
  vi.mocked(useAuth).mockReturnValue({
    user: {
      id: "admin-1",
      email: "admin@example.com",
      first_name: "Admin",
      last_name: "User",
      is_verified: true,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      is_superuser: true,
      mfa_enabled: false,
    },
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
    deleteAccount: vi.fn(),
    refetchUser: vi.fn(),
  });
  vi.mocked(useStartImpersonation).mockReturnValue({
    mutateAsync: mutateAsyncMock,
    isPending: false,
  } as unknown as ReturnType<typeof useStartImpersonation>);
});

describe("ImpersonateUserDialog", () => {
  it("navigates to the canonical candidate home after starting impersonation", async () => {
    render(<ImpersonateUserDialog user={targetUser} open onOpenChange={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Reason"), {
      target: { value: "Investigating a support request" },
    });
    fireEvent.submit(screen.getByLabelText("Reason").closest("form")!);

    await waitFor(() =>
      expect(mutateAsyncMock).toHaveBeenCalledWith({
        userId: "candidate-1",
        reason: "Investigating a support request",
        mfaCode: undefined,
      }),
    );
    expect(assignMock).toHaveBeenCalledWith("/app/matches");
  });
});
