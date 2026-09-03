import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppShell } from "./AppShell";

const unreadMatchesMock = vi.fn(() => ({ unreadCount: 4 }));

vi.mock("next/navigation", () => ({
  usePathname: () => "/app/matches",
}));
vi.mock("@/providers/auth-provider", () => ({
  useAuth: () => ({ user: null }),
}));
vi.mock("@/features/job-matching", () => ({
  useUnreadMatchEvents: () => unreadMatchesMock(),
}));
vi.mock("@/components/auth/verification-banner", () => ({
  VerificationBanner: () => null,
}));
vi.mock("@/features/admin", () => ({
  ImpersonationBanner: () => null,
}));
vi.mock("./AppSidebar", () => ({
  AppSidebar: () => null,
}));
vi.mock("./AppNavRail", () => ({
  AppNavRail: () => null,
}));
vi.mock("./AppTopbar", () => ({
  AppTopbar: ({ product }: { product: string }) => <div>{product} topbar</div>,
}));
vi.mock("./AppBottomNav", () => ({
  AppBottomNav: () => null,
}));

beforeEach(() => {
  unreadMatchesMock.mockClear();
});

describe("AppShell product subscriptions", () => {
  it("mounts the match subscription for Candidate", () => {
    render(<AppShell product="candidate">Candidate content</AppShell>);
    expect(unreadMatchesMock).toHaveBeenCalledOnce();
    expect(screen.getByText("Candidate content")).toBeInTheDocument();
  });

  it.each(["desk", "osint"] as const)(
    "does not mount Candidate subscriptions for %s",
    (product) => {
      render(<AppShell product={product}>Staff content</AppShell>);
      expect(unreadMatchesMock).not.toHaveBeenCalled();
      expect(screen.getByText(`${product} topbar`)).toBeInTheDocument();
    },
  );
});
