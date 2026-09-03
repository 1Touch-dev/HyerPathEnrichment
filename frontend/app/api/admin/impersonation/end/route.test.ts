import { beforeEach, describe, expect, it, vi } from "vitest";
import { backendFetch } from "@/src/lib/backend-client";
import { POST } from "./route";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
}));

describe("POST /api/admin/impersonation/end", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the restored admin access cookie", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      new Response(null, {
        status: 204,
        headers: {
          "Set-Cookie":
            "access_token=restored-admin-token; Max-Age=1800; Path=/; HttpOnly; SameSite=lax",
        },
      }),
    );

    const response = await POST();

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/impersonation/end", {
      method: "POST",
    });
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({ success: true, data: null });
    expect(response.headers.get("set-cookie")).toContain("access_token=restored-admin-token");
    expect(response.headers.get("set-cookie")).not.toContain("Max-Age=0");
  });
});
