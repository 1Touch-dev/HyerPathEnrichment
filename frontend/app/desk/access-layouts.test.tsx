import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FeatureFlagsLayout from "./feature-flags/layout";
import QueuesLayout from "./queues/layout";
import RolesLayout from "./roles/layout";

vi.mock("@/components/auth/admin-guard", () => ({
  AdminGuard: ({
    children,
    permission,
  }: {
    children: React.ReactNode;
    permission: { resource: string; action: string };
  }) => (
    <div data-testid="admin-guard" data-permission={`${permission.resource}:${permission.action}`}>
      {children}
    </div>
  ),
}));

describe("Desk owner-only route layouts", () => {
  it.each([
    [RolesLayout, "roles:read"],
    [FeatureFlagsLayout, "feature_flags:read"],
    [QueuesLayout, "queues:read"],
  ])("applies AdminGuard with %s", (Layout, permission) => {
    const { unmount } = render(
      <Layout>
        <div>Protected content</div>
      </Layout>,
    );

    expect(screen.getByTestId("admin-guard")).toHaveAttribute("data-permission", permission);
    unmount();
  });
});
