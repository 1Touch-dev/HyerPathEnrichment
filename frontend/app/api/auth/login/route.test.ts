import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { successEnvelope } from "@/src/lib/api-envelope";
import { POST } from "./route";

const user = {
  id: "u1",
  email: "recruiter@example.com",
  first_name: "Rae",
  last_name: "Cruiter",
  is_verified: true,
  is_active: true,
  is_superuser: false,
  role_id: "role-1",
  role_name: "recruiter",
  permissions: [{ resource: "brands", action: "read" }],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("POST /api/auth/login", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("forwards the backend envelope, identity, and cookies unchanged", async () => {
    const backendBody = successEnvelope({ user, message: "Login successful" });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(backendBody), {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            "Set-Cookie": "access_token=token; Path=/; HttpOnly",
          },
        }),
      ),
    );

    const response = await POST(
      new NextRequest("http://localhost/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: "recruiter@example.com",
          password: "SecurePass123!",
        }),
      }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual(backendBody);
    expect(response.headers.get("set-cookie")).toContain("access_token=token");
  });
});
