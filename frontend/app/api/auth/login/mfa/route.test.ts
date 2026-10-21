import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { successEnvelope } from "@/src/lib/api-envelope";
import { POST } from "./route";

describe("POST /api/auth/login/mfa", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.stubEnv("BACKEND_API_URL", "http://backend:8000");
  });

  it("forwards the challenge cookie and the session cookies", async () => {
    const backendHeaders = new Headers({ "Content-Type": "application/json" });
    const accessCookie = "access_token=access; Path=/; HttpOnly; SameSite=Lax";
    const refreshCookie = "refresh_token=refresh; Path=/; HttpOnly; SameSite=Strict";
    backendHeaders.append("Set-Cookie", accessCookie);
    backendHeaders.append("Set-Cookie", refreshCookie);
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify(successEnvelope({ user: { id: "u1" }, message: "Login successful" })),
        {
          status: 200,
          headers: backendHeaders,
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest("http://localhost/api/auth/login/mfa", {
        method: "POST",
        headers: { cookie: "mfa_login=challenge" },
        body: JSON.stringify({ code: "123456" }),
      }),
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://backend:8000/auth/login/mfa",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ cookie: "mfa_login=challenge" }),
      }),
    );
    expect(response.headers.getSetCookie()).toEqual([accessCookie, refreshCookie]);
  });
});
