import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { cookies } from "next/headers";
import { successEnvelope } from "@/src/lib/api-envelope";
import { POST } from "./route";

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

describe("POST /api/auth/refresh", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "refresh-token" }),
    } as never);
  });

  it("forwards the refreshed identity envelope and rotated cookies", async () => {
    const backendBody = successEnvelope({
      user: {
        id: "u1",
        role_id: "role-1",
        role_name: "recruiter",
        permissions: [{ resource: "brands", action: "read" }],
        is_superuser: false,
      },
      message: "Token refreshed successfully",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(backendBody), {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            "Set-Cookie": "refresh_token=rotated; Path=/; HttpOnly",
          },
        }),
      ),
    );

    const response = await POST(
      new NextRequest("http://localhost/api/auth/refresh", { method: "POST" }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual(backendBody);
    expect(response.headers.get("set-cookie")).toContain("refresh_token=rotated");
  });
});
