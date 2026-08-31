import { describe, it, expect } from "vitest";
import {
  getTierCopy,
  isComingSoonConfig,
  parseBrandLandingConfig,
  serializeBrandLandingConfig,
} from "./brand-landing-config";

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

describe("serializeBrandLandingConfig", () => {
  it("round-trips general copy plus a tier map using cta_label on the wire", () => {
    const raw = {
      headline: "Join Acme",
      cta_label: "Apply",
      free: { headline: "Free desk", cta_label: "Start free" },
      premium: { cta_label: "Go premium" },
    };
    const parsed = parseBrandLandingConfig(raw);
    const result = serializeBrandLandingConfig(parsed, {
      previousWasObject: true,
      isCreate: false,
    });

    expect(result).toEqual({ ok: true, value: raw });
    if (result.ok && result.value) {
      expect(result.value).not.toHaveProperty("tiers");
      expect(result.value).not.toHaveProperty("_default");
      expect(parseBrandLandingConfig(result.value)).toEqual(parsed);
    }
  });

  it("loads { headline, tiers: [free] } as general copy only and serializes without a free tier", () => {
    const parsed = parseBrandLandingConfig({
      headline: "Join Acme",
      tiers: ["free"],
    });
    expect(parsed.generalCopy).toEqual({ headline: "Join Acme" });
    expect(getTierCopy(parsed, "free")).toBeNull();

    const result = serializeBrandLandingConfig(parsed, {
      previousWasObject: true,
      isCreate: false,
    });
    expect(result).toEqual({ ok: true, value: { headline: "Join Acme" } });
    if (result.ok && result.value) {
      expect(result.value).not.toHaveProperty("tiers");
      expect(result.value).not.toHaveProperty("free");
    }
  });

  it("rejects reserved slugs", () => {
    for (const slug of ["tiers", "headline", "cta_label", "_default"]) {
      const result = serializeBrandLandingConfig(
        { generalCopy: null, tiers: { [slug]: { headline: "nope" } } },
        { previousWasObject: false, isCreate: true },
      );
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toContain(slug);
      }
    }
  });

  it("rejects slugs that fail ^[a-z0-9-]+$", () => {
    const result = serializeBrandLandingConfig(
      { generalCopy: null, tiers: { "Free Plan": { headline: "nope" } } },
      { previousWasObject: false, isCreate: true },
    );
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toMatch(/Free Plan/);
    }
  });

  it("omits on create when general copy and tiers are empty", () => {
    expect(
      serializeBrandLandingConfig(
        { generalCopy: null, tiers: {} },
        { previousWasObject: false, isCreate: true },
      ),
    ).toEqual({ ok: true, value: undefined });
  });

  it("omits when empty and previously null, rather than writing null", () => {
    expect(
      serializeBrandLandingConfig(
        { generalCopy: null, tiers: {} },
        { previousWasObject: false, isCreate: false },
      ),
    ).toEqual({ ok: true, value: undefined });
  });

  it("returns null when the user cleared a previous object", () => {
    expect(
      serializeBrandLandingConfig(
        { generalCopy: null, tiers: {} },
        { previousWasObject: true, isCreate: false },
      ),
    ).toEqual({ ok: true, value: null });
  });

  it("emits _default-parsed copy at top level, not as _default", () => {
    const parsed = parseBrandLandingConfig({
      headline: "Top-level headline",
      _default: { headline: "Default wins", cta_label: "Apply" },
    });
    const result = serializeBrandLandingConfig(parsed, {
      previousWasObject: true,
      isCreate: false,
    });
    expect(result).toEqual({
      ok: true,
      value: { headline: "Default wins", cta_label: "Apply" },
    });
  });
});
