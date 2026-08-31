import { describe, it, expect } from "vitest";
import { getTierCopy, isComingSoonConfig, parseBrandLandingConfig } from "./brand-landing-config";

describe("parseBrandLandingConfig", () => {
  it("treats null as coming soon with no tiers", () => {
    const parsed = parseBrandLandingConfig(null);
    expect(isComingSoonConfig(parsed)).toBe(true);
    expect(parsed.generalCopy).toBeNull();
    expect(parsed.tiers).toEqual({});
  });

  it("treats {} as coming soon with no tiers", () => {
    const parsed = parseBrandLandingConfig({});
    expect(isComingSoonConfig(parsed)).toBe(true);
    expect(getTierCopy(parsed, "free")).toBeNull();
  });

  it("does not treat the shipped public-test blob as coming-soon; reserved tiers key is not a tier", () => {
    const parsed = parseBrandLandingConfig({
      headline: "Join Acme",
      tiers: ["free"],
    });

    expect(isComingSoonConfig(parsed)).toBe(false);
    expect(parsed.generalCopy).toEqual({ headline: "Join Acme" });
    expect(getTierCopy(parsed, "free")).toBeNull();
    expect(getTierCopy(parsed, "tiers")).toBeNull();
  });

  it("lets _default copy win over a top-level headline", () => {
    const parsed = parseBrandLandingConfig({
      headline: "Top-level headline",
      _default: { headline: "Default wins", cta_label: "Apply" },
    });

    expect(isComingSoonConfig(parsed)).toBe(false);
    expect(parsed.generalCopy).toEqual({
      headline: "Default wins",
      ctaLabel: "Apply",
    });
    expect(getTierCopy(parsed, "_default")).toBeNull();
  });

  it("treats a tier-only map as coming soon on the general page and a live tier URL", () => {
    const parsed = parseBrandLandingConfig({
      premium: { headline: "Premium desk", cta_label: "Join premium" },
    });

    expect(isComingSoonConfig(parsed)).toBe(true);
    expect(getTierCopy(parsed, "premium")).toEqual({
      headline: "Premium desk",
      ctaLabel: "Join premium",
    });
  });

  it("does not treat { premium: { body } } as a tier", () => {
    const parsed = parseBrandLandingConfig({
      premium: { body: "Not a copy object" },
    });

    expect(isComingSoonConfig(parsed)).toBe(true);
    expect(getTierCopy(parsed, "premium")).toBeNull();
  });

  it("treats an object-valued key with headline or cta_label as a tier when not reserved", () => {
    const parsed = parseBrandLandingConfig({
      headline: "General",
      free: { cta_label: "Start free" },
    });

    expect(parsed.generalCopy).toEqual({ headline: "General" });
    expect(getTierCopy(parsed, "free")).toEqual({ ctaLabel: "Start free" });
  });

  it("never falls back to general copy when the tier key has no copy-object", () => {
    const parsed = parseBrandLandingConfig({
      headline: "General only",
      empty: { body: "nope" },
    });

    expect(getTierCopy(parsed, "empty")).toBeNull();
    expect(getTierCopy(parsed, "missing")).toBeNull();
    expect(getTierCopy(parsed, "headline")).toBeNull();
    expect(getTierCopy(parsed, "cta_label")).toBeNull();
  });
});
