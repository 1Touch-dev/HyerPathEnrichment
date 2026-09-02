import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { successEnvelope } from "@/src/lib/api-envelope";
import { POST } from "./route";

describe("POST /api/auth/login multi-cookie forwarding", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("forwards both backend authentication cookies as separate Set-Cookie values", async () => {
    const backendHeaders = new Headers({ "Content-Type": "application/json" });
    const accessCookie = "access_token=access; Path=/; HttpOnly; SameSite=Lax";
    const refreshCookie = "refresh_token=refresh; Path=/; HttpOnly; SameSite=Lax";
    backendHeaders.append("Set-Cookie", accessCookie);
    backendHeaders.append("Set-Cookie", refreshCookie);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify(
            successEnvelope({
              user: {
                id: "u1",
                role_id: "role-1",
                role_name: "recruiter",
                permissions: [],
                is_superuser: false,
              },
              message: "Login successful",
            }),
          ),
          { status: 200, headers: backendHeaders },
        ),
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

    expect(response.headers.getSetCookie()).toEqual([accessCookie, refreshCookie]);
  });
});
