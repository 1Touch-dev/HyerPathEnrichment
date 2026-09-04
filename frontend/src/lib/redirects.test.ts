import { describe, expect, it } from "vitest";

// @ts-expect-error next.config.js is the CommonJS runtime configuration.
import nextConfigModule from "../../next.config.js";

const nextConfig = nextConfigModule as {
  redirects: () => Promise<Array<{ source: string; destination: string; permanent: boolean }>>;
};

const expectedRedirects = [
  { source: "/app/enrich", destination: "/osint", permanent: false },
  { source: "/app/signals", destination: "/desk/signals", permanent: false },
  { source: "/app/admin", destination: "/desk", permanent: false },
  { source: "/app/admin/:path*", destination: "/desk/:path*", permanent: false },
] as const;

describe("compatibility redirects", () => {
  it("defines the complete temporary redirect inventory", async () => {
    await expect(nextConfig.redirects()).resolves.toEqual(expectedRedirects);
  });

  it("preserves nested legacy Desk paths", async () => {
    const redirects = await nextConfig.redirects();

    expect(redirects).toContainEqual({
      source: "/app/admin/:path*",
      destination: "/desk/:path*",
      permanent: false,
    });
  });

  it("does not redirect Candidate-owned routes", async () => {
    const redirects = await nextConfig.redirects();
    const sources = redirects.map(({ source }) => source);

    expect(sources).not.toEqual(
      expect.arrayContaining([
        "/app/jobs",
        "/app/jobs/:id",
        "/app/history",
        "/app/dashboard",
        "/app/health",
      ]),
    );
  });

  it("leaves query strings untouched for Next.js to forward", async () => {
    const redirects = await nextConfig.redirects();

    expect(redirects.every(({ destination }) => !destination.includes("?"))).toBe(true);
  });
});
