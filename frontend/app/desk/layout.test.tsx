import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DeskLayout from "./layout";

vi.mock("@/components/auth/staff-guard", () => ({
  StaffGuard: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="staff-guard">{children}</div>
  ),
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children, product }: { children: React.ReactNode; product: string }) => (
    <div data-product={product}>{children}</div>
  ),
}));

describe("DeskLayout", () => {
  it("mounts the Desk shell behind the staff guard", () => {
    render(
      <DeskLayout>
        <div>Desk content</div>
      </DeskLayout>,
    );

    expect(screen.getByTestId("staff-guard")).toContainElement(screen.getByText("Desk content"));
    expect(screen.getByText("Desk content").parentElement).toHaveAttribute("data-product", "desk");
  });
});
