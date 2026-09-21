import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FeatureFlagsLayout from "./feature-flags/layout";
import QueuesLayout from "./queues/layout";
import RolesLayout from "./roles/layout";

// Structural wiring only — owner/permission semantics live in AdminGuard.test.tsx
// (and product-doors unit coverage). Do not treat this mock as AuthZ proof.
vi.mock("@/components/auth/admin-guard", () => ({
  AdminGuard: ({
    children,
    permission,
  }: {
    children: React.ReactNode;
    permission?: { resource: string; action: string };
  }) => (
    <div
      data-testid="admin-guard"
      data-permission={permission ? `${permission.resource}:${permission.action}` : undefined}
    >
      {children}
    </div>
  ),
}));

describe("Desk privileged route layouts", () => {
  it.each([
    [RolesLayout, "roles:read"],
    [FeatureFlagsLayout, "feature_flags:read"],
    [QueuesLayout, "queues:read"],
  ] as const)("wraps the page in AdminGuard with %s permission wiring", (Layout, permission) => {
    const { unmount } = render(
      <Layout>
        <div>Protected content</div>
      </Layout>,
    );

    expect(screen.getByTestId("admin-guard")).toHaveAttribute("data-permission", permission);
    unmount();
  });
});
