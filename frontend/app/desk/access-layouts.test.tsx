import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FeatureFlagsLayout from "./feature-flags/layout";
import QueuesLayout from "./queues/layout";
import RolesLayout from "./roles/layout";

vi.mock("@/components/auth/admin-guard", () => ({
  AdminGuard: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="admin-guard">{children}</div>
  ),
}));

describe("Desk owner-only route layouts", () => {
  it.each([RolesLayout, FeatureFlagsLayout, QueuesLayout])(
    "applies the owner-only AdminGuard",
    (Layout) => {
      const { unmount } = render(
        <Layout>
          <div>Protected content</div>
        </Layout>,
      );

      expect(screen.getByTestId("admin-guard")).not.toHaveAttribute("data-permission");
      unmount();
    },
  );
});
