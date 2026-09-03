import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppTopbar } from "./AppTopbar";
import { getNavSections } from "./nav-config";

vi.mock("next/navigation", () => ({
  usePathname: () => "/osint/settings",
}));
vi.mock("@/components/console/HealthIndicator", () => ({
  HealthIndicator: () => null,
}));
vi.mock("@/components/auth/user-menu", () => ({
  UserMenu: () => null,
}));

describe("AppTopbar product chip", () => {
  it("uses the Figma product-chip treatment and active section label", () => {
    render(<AppTopbar product="osint" sections={getNavSections("osint", null)} />);

    const chip = screen.getByText("OSINT");
    expect(chip).toHaveClass(
      "rounded-md",
      "bg-secondary",
      "px-2.5",
      "py-1",
      "text-sm",
      "font-medium",
      "leading-5",
      "text-primary",
    );
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });
});
