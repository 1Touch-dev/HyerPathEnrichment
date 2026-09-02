import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { cookies } from "next/headers";
import { successEnvelope } from "@/src/lib/api-envelope";
import { GET } from "./route";

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

vi.mock("@/src/lib/mocks/enabled", () => ({
  isMockMode: () => false,
}));

describe("GET /api/auth/me", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "access-token" }),
    } as never);
  });

  it("forwards the backend user envelope without changing identity fields", async () => {
    const backendBody = successEnvelope({
      id: "u1",
      role_id: "role-1",
      role_name: "recruiter",
      permissions: [{ resource: "brands", action: "read" }],
      is_superuser: false,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(backendBody), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const response = await GET(new NextRequest("http://localhost/api/auth/me"));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual(backendBody);
  });
});
