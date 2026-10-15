import { afterEach, describe, expect, it, vi } from "vitest";
import { getPublicAppOrigin, publicAppUrl } from "./public-app-url";

describe("getPublicAppOrigin", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("prefers APP_PUBLIC_URL over request origin", () => {
    vi.stubEnv("APP_PUBLIC_URL", "https://app.hyerpath.com/");
    vi.stubEnv("NODE_ENV", "production");
    expect(
      getPublicAppOrigin({ nextUrl: { origin: "https://localhost:3000" } }),
    ).toBe("https://app.hyerpath.com");
  });

  it("falls back to NEXT_PUBLIC_APP_URL when APP_PUBLIC_URL is unset", () => {
    vi.stubEnv("APP_PUBLIC_URL", "");
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://app.hyerpath.com");
    vi.stubEnv("NODE_ENV", "production");
    expect(getPublicAppOrigin()).toBe("https://app.hyerpath.com");
  });

  it("uses request origin in non-production when unset", () => {
    vi.stubEnv("APP_PUBLIC_URL", "");
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "");
    vi.stubEnv("NODE_ENV", "development");
    expect(
      getPublicAppOrigin({ nextUrl: { origin: "http://localhost:3000" } }),
    ).toBe("http://localhost:3000");
  });

  it("rejects missing production configuration instead of localhost", () => {
    vi.stubEnv("APP_PUBLIC_URL", "");
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "");
    vi.stubEnv("NODE_ENV", "production");
    expect(() =>
      getPublicAppOrigin({ nextUrl: { origin: "https://localhost:3000" } }),
    ).toThrow(/APP_PUBLIC_URL must be set/);
  });

  it("rejects localhost APP_PUBLIC_URL in production", () => {
    vi.stubEnv("APP_PUBLIC_URL", "https://localhost:3000");
    vi.stubEnv("NODE_ENV", "production");
    expect(() => getPublicAppOrigin()).toThrow(/must not point at localhost/);
  });

  it("builds absolute paths on the public origin", () => {
    vi.stubEnv("APP_PUBLIC_URL", "https://app.hyerpath.com");
    vi.stubEnv("NODE_ENV", "production");
    const url = publicAppUrl("/login?error=access_denied");
    expect(url.toString()).toBe("https://app.hyerpath.com/login?error=access_denied");
  });
});
