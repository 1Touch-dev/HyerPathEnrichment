import { existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const deskPages = [
  "page.tsx",
  "ai-actions/page.tsx",
  "analytics/page.tsx",
  "audit-logs/page.tsx",
  "brands/page.tsx",
  "demand-intelligence/page.tsx",
  "documents/page.tsx",
  "feature-flags/page.tsx",
  "job-postings/page.tsx",
  "linkedin-tasks/page.tsx",
  "outreach/page.tsx",
  "portfolio/page.tsx",
  "queues/page.tsx",
  "review-queue/page.tsx",
  "roles/page.tsx",
  "signals/page.tsx",
  "sourcing-leads/page.tsx",
  "staff-invites/page.tsx",
  "system-health/page.tsx",
  "users/page.tsx",
  "users/[userId]/page.tsx",
] as const;

describe("Desk route inventory", () => {
  it.each(deskPages)("provides /desk/%s", (relativePath) => {
    expect(existsSync(join(process.cwd(), "app/desk", relativePath))).toBe(true);
  });

  it("removes the obsolete source implementations", () => {
    expect(existsSync(join(process.cwd(), "app/app/admin"))).toBe(false);
    expect(existsSync(join(process.cwd(), "app/app/signals"))).toBe(false);
  });
});
