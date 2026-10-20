import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "./route";

describe("GET /callback/google", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.stubEnv("APP_PUBLIC_URL", "https://app.hyerpath.com");
    vi.stubEnv("BACKEND_API_URL", "http://backend:8000");
    vi.stubEnv("NODE_ENV", "production");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("redirects access_denied to the public login origin", async () => {
    const response = await GET(
      new NextRequest("https://localhost:3000/callback/google?error=access_denied"),
    );
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://app.hyerpath.com/login?error=access_denied",
    );
  });

  it("redirects missing code to google_oauth_denied on the public origin", async () => {
    const response = await GET(new NextRequest("https://localhost:3000/callback/google"));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://app.hyerpath.com/login?error=google_oauth_denied",
    );
  });

  it("redirects backend 400 failures to google_oauth_failed on the public origin", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Google OAuth login failed" }), {
          status: 400,
        }),
      ),
    );

    const response = await GET(
      new NextRequest("https://localhost:3000/callback/google?code=abc&state=1.sig"),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://app.hyerpath.com/login?error=google_oauth_failed",
    );
  });

  it("redirects backend 500 failures to google_oauth_failed on the public origin", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("boom", { status: 500 })));

    const response = await GET(
      new NextRequest("https://localhost:3000/callback/google?code=abc&state=1.sig"),
    );

    expect(response.headers.get("location")).toBe(
      "https://app.hyerpath.com/login?error=google_oauth_failed",
    );
  });

  it("redirects fetch exceptions to google_oauth_failed on the public origin", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("timeout")));

    const response = await GET(
      new NextRequest("https://localhost:3000/callback/google?code=abc&state=1.sig"),
    );

    expect(response.headers.get("location")).toBe(
      "https://app.hyerpath.com/login?error=google_oauth_failed",
    );
  });

  it("sends an enrolled MFA user back to login without opening the app", async () => {
    const backendHeaders = new Headers({ "Content-Type": "application/json" });
    backendHeaders.append("Set-Cookie", "mfa_login=challenge; Path=/; HttpOnly; SameSite=Strict");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ mfa_required: true, user: null, message: "code" }), {
          status: 200,
          headers: backendHeaders,
        }),
      ),
    );

    const response = await GET(
      new NextRequest("https://localhost:3000/callback/google?code=abc&state=1.sig"),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://app.hyerpath.com/login?mfa=required");
    expect(response.headers.get("set-cookie")).toContain("mfa_login=challenge");
  });

  it("on success redirects to the post-login path and forwards cookies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            user: { is_superuser: false },
            message: "Google login successful",
          }),
          {
            status: 200,
            headers: {
              "Content-Type": "application/json",
              "Set-Cookie": "access_token=tok; Path=/; HttpOnly; Secure",
            },
          },
        ),
      ),
    );

    const response = await GET(
      new NextRequest("https://localhost:3000/callback/google?code=abc&state=1.sig"),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://app.hyerpath.com/app/matches");
    expect(response.headers.get("set-cookie")).toContain("access_token=tok");
  });

  it("uses local origin in development when APP_PUBLIC_URL is unset", async () => {
    vi.stubEnv("APP_PUBLIC_URL", "");
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "");
    vi.stubEnv("NODE_ENV", "development");

    const response = await GET(
      new NextRequest("http://localhost:3000/callback/google?error=access_denied"),
    );

    expect(response.headers.get("location")).toBe(
      "http://localhost:3000/login?error=access_denied",
    );
  });
});
