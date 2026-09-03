import { expect, test } from "@playwright/test";

const redirectCases = [
  ["/app/enrich", "/osint"],
  ["/app/history", "/osint/jobs"],
  ["/app/jobs", "/osint/jobs"],
  ["/app/jobs/dossier-123", "/osint/jobs/dossier-123"],
  ["/app/signals", "/desk/signals"],
  ["/app/dashboard", "/osint"],
  ["/app/health", "/desk/system-health"],
  ["/app/admin", "/desk"],
  ["/app/admin/system-health", "/desk/system-health"],
] as const;

test.describe("temporary product door redirects", () => {
  for (const [source, target] of redirectCases) {
    test(`${source} redirects to ${target} with 307`, async ({ request }) => {
      const response = await request.get(source, { maxRedirects: 0 });

      expect(response.status()).toBe(307);
      expect(new URL(response.headers().location, "http://127.0.0.1:3000").pathname).toBe(target);
    });
  }

  test("dynamic IDs and query strings survive", async ({ request }) => {
    const response = await request.get("/app/jobs/dossier-123?tiers=tier2&view=raw", {
      maxRedirects: 0,
    });
    const location = new URL(response.headers().location, "http://127.0.0.1:3000");

    expect(response.status()).toBe(307);
    expect(location.pathname).toBe("/osint/jobs/dossier-123");
    expect(location.searchParams.get("tiers")).toBe("tier2");
    expect(location.searchParams.get("view")).toBe("raw");
  });
});
