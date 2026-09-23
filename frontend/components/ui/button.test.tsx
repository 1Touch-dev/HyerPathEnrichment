import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button, buttonVariants } from "./button";

describe("Button contrast lock", () => {
  it("uses primary-foreground on primary fill", () => {
    render(<Button>Save</Button>);
    const btn = screen.getByRole("button", { name: "Save" });
    expect(btn).toHaveClass("bg-primary", "text-primary-foreground");
  });

  it("uses destructive-foreground on destructive fill", () => {
    render(<Button variant="destructive">Delete</Button>);
    const btn = screen.getByRole("button", { name: "Delete" });
    expect(btn).toHaveClass("bg-destructive", "text-destructive-foreground");
  });

  it("keeps outline/secondary on surface with border (no ink-on-primary)", () => {
    expect(buttonVariants({ variant: "outline" })).toContain("bg-surface");
    expect(buttonVariants({ variant: "outline" })).toContain("border-border");
    expect(buttonVariants({ variant: "secondary" })).toContain("bg-surface");
    expect(buttonVariants({ variant: "default" })).toContain("text-primary-foreground");
    expect(buttonVariants({ variant: "destructive" })).toContain("text-destructive-foreground");
  });
});
