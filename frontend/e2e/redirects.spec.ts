import { expect, test } from "@playwright/test";

const redirectCases = [
  ["/app/enrich?tiers=tier1", "/osint?tiers=tier1"],
  ["/app/signals?source=webhook", "/desk/signals?source=webhook"],
  ["/app/admin", "/desk"],
  ["/app/admin/system-health?probe=redis", "/desk/system-health?probe=redis"],
] as const;

const directCandidateCases = [
  "/app/jobs?state=queued",
  "/app/history?cursor=next",
  "/app/jobs/dossier-123?tiers=tier2&view=raw",
  "/app/dashboard?range=7d",
  "/app/health?probe=bff",
] as const;

test.describe("temporary product door redirects", () => {
  for (const [source, target] of redirectCases) {
    test(`${source} redirects to ${target} with 307`, async ({ request }) => {
      const response = await request.get(source, { maxRedirects: 0 });
      const location = new URL(response.headers().location, "http://127.0.0.1:3000");
      const expected = new URL(target, "http://127.0.0.1:3000");

      expect(response.status()).toBe(307);
      expect(location.pathname).toBe(expected.pathname);
      expect(location.search).toBe(expected.search);
    });
  }

  test("Candidate routes remain direct pages and preserve deep links and queries", async ({
    request,
  }) => {
    test.setTimeout(90_000);

    for (const source of directCandidateCases) {
      const response = await request.get(source, { maxRedirects: 0 });
      const current = new URL(response.url());
      const expected = new URL(source, "http://127.0.0.1:3000");

      expect(response.status()).toBe(200);
      expect(current.pathname).toBe(expected.pathname);
      expect(current.search).toBe(expected.search);
    }
  });
});
