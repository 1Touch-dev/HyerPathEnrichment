import { NextRequest, NextResponse } from "next/server";
import { publicAppUrl } from "@/src/lib/public-app-url";

/**
 * Browser-facing start of Google OAuth.
 * Asks the API for an authorization URL, then redirects the browser to Google.
 * Never redirect the browser to BACKEND_API_URL (loopback on this host).
 */
export async function GET(request: NextRequest) {
  const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8000";

  try {
    const response = await fetch(`${backendUrl}/auth/google/authorize`, {
      method: "GET",
      cache: "no-store",
    });

    if (!response.ok) {
      const detail = await response.text();
      console.error("Google authorize failed:", response.status, detail);
      const login = publicAppUrl("/login", request);
      login.searchParams.set("error", "google_oauth_unavailable");
      return NextResponse.redirect(login);
    }

    const data = (await response.json()) as { authorization_url?: string };
    if (!data.authorization_url) {
      const login = publicAppUrl("/login", request);
      login.searchParams.set("error", "google_oauth_unavailable");
      return NextResponse.redirect(login);
    }

    return NextResponse.redirect(data.authorization_url);
  } catch (error) {
    console.error("Google authorize error:", error);
    const login = publicAppUrl("/login", request);
    login.searchParams.set("error", "google_oauth_unavailable");
    return NextResponse.redirect(login);
  }
}
