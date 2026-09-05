import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UserDetailDrawer } from "./UserDetailDrawer";

vi.mock("./AuditLogTable", () => ({
  AuditLogTable: ({ targetId }: { targetId: string }) => <div>Audit log for {targetId}</div>,
}));

describe("UserDetailDrawer", () => {
  it("shows role details as read-only during Wave 2", () => {
    render(
      <UserDetailDrawer
        user={{
          id: "user-1",
          email: "user@example.com",
          firstName: "Test",
          lastName: "User",
          isActive: true,
          isVerified: true,
          isSuperuser: false,
          roleId: "role-1",
          roleName: "support",
          mfaEnabled: false,
          createdAt: "2026-01-01T00:00:00Z",
          deletedAt: null,
        }}
        open
        onOpenChange={vi.fn()}
      />,
    );

    expect(screen.getByText("Support")).toBeInTheDocument();
    expect(
      screen.getByText(/Role assignment is unavailable in Wave 2 until ADR21 `P3` controls/i),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Select role")).not.toBeInTheDocument();
  });
});
