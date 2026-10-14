import { NextRequest, NextResponse } from "next/server";
import { forwardBackendSetCookies } from "@/src/lib/forward-backend-cookies";
import { type ProductDoorUser, resolvePostLoginPath } from "@/src/lib/product-doors";

/**
 * Google redirects here (GOOGLE_OAUTH_REDIRECT_URL).
 * Exchange the code via the API BFF-style and set HttpOnly cookies.
 */
export async function GET(request: NextRequest) {
  const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
  const origin = request.nextUrl.origin;
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const oauthError = request.nextUrl.searchParams.get("error");

  if (oauthError || !code) {
    const login = new URL("/login", origin);
    login.searchParams.set("error", oauthError || "google_oauth_denied");
    return NextResponse.redirect(login);
  }

  const callbackUrl = new URL(`${backendUrl}/auth/google/callback`);
  callbackUrl.searchParams.set("code", code);
  if (state) {
    callbackUrl.searchParams.set("state", state);
  }

  try {
    const response = await fetch(callbackUrl.toString(), {
      method: "GET",
      cache: "no-store",
    });

    if (!response.ok) {
      const detail = await response.text();
      console.error("Google callback failed:", response.status, detail);
      const login = new URL("/login", origin);
      login.searchParams.set("error", "google_oauth_failed");
      return NextResponse.redirect(login);
    }

    const data = (await response.json()) as { user?: ProductDoorUser };
    const user: ProductDoorUser = data.user ?? { is_superuser: false };
    const destination = resolvePostLoginPath(user, null);
    const nextResponse = NextResponse.redirect(new URL(destination, origin));
    forwardBackendSetCookies(response, nextResponse);
    return nextResponse;
  } catch (error) {
    console.error("Google callback error:", error);
    const login = new URL("/login", origin);
    login.searchParams.set("error", "google_oauth_failed");
    return NextResponse.redirect(login);
  }
}
