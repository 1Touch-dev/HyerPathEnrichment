import { describe, it, expect } from "vitest";
import { resolveSubdomainRewrite } from "./subdomain";

describe("resolveSubdomainRewrite", () => {
  const rootDomain = "hyrepath.dev";

  it("returns the rewrite path for a matching subdomain when enabled", () => {
    expect(resolveSubdomainRewrite("jane-doe.hyrepath.dev", true, rootDomain)).toBe("/p/jane-doe");
  });

  it("returns null for a non-matching host", () => {
    expect(resolveSubdomainRewrite("example.com", true, rootDomain)).toBeNull();
  });

  it("returns null when disabled, even for a matching host", () => {
    expect(resolveSubdomainRewrite("jane-doe.hyrepath.dev", false, rootDomain)).toBeNull();
  });

  it("returns null for the bare root domain itself (no subdomain)", () => {
    expect(resolveSubdomainRewrite("hyrepath.dev", true, rootDomain)).toBeNull();
  });

  it("is case-insensitive on both host and root domain", () => {
    expect(resolveSubdomainRewrite("Jane-Doe.HYREPATH.DEV", true, rootDomain)).toBe("/p/jane-doe");
  });

  it("strips a trailing port before matching", () => {
    expect(resolveSubdomainRewrite("jane-doe.hyrepath.dev:3000", true, rootDomain)).toBe(
      "/p/jane-doe",
    );
  });

  it("returns null for a host that only shares a suffix but isn't a proper subdomain", () => {
    expect(resolveSubdomainRewrite("nothyrepath.dev", true, rootDomain)).toBeNull();
  });

  it("returns null for an empty host", () => {
    expect(resolveSubdomainRewrite("", true, rootDomain)).toBeNull();
  });
});
