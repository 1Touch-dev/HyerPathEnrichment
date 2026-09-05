import { describe, expect, it, vi } from "vitest";
import { backendFetch } from "@/src/lib/backend-client";
import { PUT } from "./route";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
  backendFetchPublic: vi.fn(),
}));

describe("PUT /api/admin/feature-flags/[key]", () => {
  it("denies mutation with a stable read-only error", async () => {
    const response = PUT();

    expect(response.status).toBe(405);
    await expect(response.json()).resolves.toMatchObject({
      success: false,
      error: {
        code: "FEATURE_FLAGS_READ_ONLY",
        message: "Feature flag mutation is disabled until an application consumer exists.",
        status_code: 405,
      },
    });
  });

  it("never forwards a mutation to the backend", () => {
    PUT();

    expect(backendFetch).not.toHaveBeenCalled();
  });
});
