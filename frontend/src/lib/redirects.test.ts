import { describe, expect, it } from "vitest";

const nextConfig = require("../../next.config.js") as {
  redirects: () => Promise<Array<{ source: string; destination: string; permanent: boolean }>>;
};

const expectedRedirects = [
  { source: "/app/enrich", destination: "/osint", permanent: false },
  { source: "/app/history", destination: "/osint/jobs", permanent: false },
  { source: "/app/jobs", destination: "/osint/jobs", permanent: false },
  { source: "/app/jobs/:id", destination: "/osint/jobs/:id", permanent: false },
  { source: "/app/signals", destination: "/desk/signals", permanent: false },
  { source: "/app/dashboard", destination: "/osint", permanent: false },
  { source: "/app/health", destination: "/desk/system-health", permanent: false },
  { source: "/app/admin", destination: "/desk", permanent: false },
  { source: "/app/admin/:path*", destination: "/desk/:path*", permanent: false },
] as const;

describe("compatibility redirects", () => {
  it("defines the complete temporary redirect inventory", async () => {
    await expect(nextConfig.redirects()).resolves.toEqual(expectedRedirects);
  });

  it("preserves dynamic dossier IDs and nested Desk paths", async () => {
    const redirects = await nextConfig.redirects();

    expect(redirects).toContainEqual({
      source: "/app/jobs/:id",
      destination: "/osint/jobs/:id",
      permanent: false,
    });
    expect(redirects).toContainEqual({
      source: "/app/admin/:path*",
      destination: "/desk/:path*",
      permanent: false,
    });
  });

  it("leaves query strings untouched for Next.js to forward", async () => {
    const redirects = await nextConfig.redirects();

    expect(redirects.every(({ destination }) => !destination.includes("?"))).toBe(true);
  });
});
