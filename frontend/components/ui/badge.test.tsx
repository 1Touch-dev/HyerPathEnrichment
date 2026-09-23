import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge, badgeVariants } from "./badge";

describe("Badge status variants", () => {
  it("locks primary solid to primary-foreground", () => {
    render(<Badge>Primary</Badge>);
    expect(screen.getByText("Primary")).toHaveClass("bg-primary", "text-primary-foreground");
  });

  it("maps soft status chips to *-soft fills", () => {
    expect(badgeVariants({ variant: "success" })).toContain("bg-success-soft");
    expect(badgeVariants({ variant: "success" })).toContain("text-success");
    expect(badgeVariants({ variant: "info" })).toContain("bg-info-soft");
    expect(badgeVariants({ variant: "warning" })).toContain("bg-warning-soft");
    expect(badgeVariants({ variant: "destructive" })).toContain("bg-destructive-soft");
    expect(badgeVariants({ variant: "destructive" })).toContain("text-destructive");
  });

  it("exposes solid status variants with foreground text", () => {
    expect(badgeVariants({ variant: "destructive-solid" })).toContain("bg-destructive");
    expect(badgeVariants({ variant: "destructive-solid" })).toContain(
      "text-destructive-foreground",
    );
    expect(badgeVariants({ variant: "success-solid" })).toContain("text-success-foreground");
  });
});
