import { describe, expect, it } from "vitest";
import { cardVariants } from "./card";

describe("Card utilities", () => {
  it("defaults to white surface without pastel KPI fills", () => {
    expect(cardVariants({ variant: "default" })).toContain("bg-surface");
    expect(cardVariants({ variant: "default" })).toContain("rounded-xl");
    expect(cardVariants({ variant: "default" })).not.toMatch(/pastel/);
  });

  it("provides violet accent and soft utilities", () => {
    expect(cardVariants({ variant: "accent" })).toContain("border-primary/25");
    expect(cardVariants({ variant: "accent" })).toContain("bg-surface");
    expect(cardVariants({ variant: "soft" })).toContain("bg-primary-soft");
  });
});
