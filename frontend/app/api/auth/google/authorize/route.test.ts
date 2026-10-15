import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "./route";

describe("GET /api/auth/google/authorize", () => {
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

  it("redirects to Google authorization URL on success", async () => {
    const authorizationUrl = "https://accounts.google.com/o/oauth2/v2/auth?client_id=x";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ authorization_url: authorizationUrl }), {
          status: 200,
        }),
      ),
    );

    const response = await GET(new NextRequest("https://localhost:3000/api/auth/google/authorize"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(authorizationUrl);
  });

  it("redirects backend failures to public login origin", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("unavailable", { status: 503 })));

    const response = await GET(new NextRequest("https://localhost:3000/api/auth/google/authorize"));

    expect(response.headers.get("location")).toBe(
      "https://app.hyerpath.com/login?error=google_oauth_unavailable",
    );
  });
});
