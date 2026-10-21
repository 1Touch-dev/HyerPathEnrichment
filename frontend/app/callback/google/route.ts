import { NextRequest, NextResponse } from "next/server";
import { forwardBackendSetCookies } from "@/src/lib/forward-backend-cookies";
import { type ProductDoorUser, resolvePostLoginPath } from "@/src/lib/product-doors";
import { publicAppUrl } from "@/src/lib/public-app-url";

function redirectToLogin(request: NextRequest, error: string): NextResponse {
  const login = publicAppUrl("/login", request);
  login.searchParams.set("error", error);
  return NextResponse.redirect(login);
}

/**
 * Google redirects here (GOOGLE_OAUTH_REDIRECT_URL).
 * Exchange the code via the API BFF-style and set HttpOnly cookies.
 */
export async function GET(request: NextRequest) {
  const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const oauthError = request.nextUrl.searchParams.get("error");
  const correlationId =
    request.headers.get("x-request-id") ||
    request.headers.get("x-correlation-id") ||
    crypto.randomUUID();

  console.info("oauth_callback_received", {
    correlationId,
    hasCode: Boolean(code),
    hasState: Boolean(state),
    oauthError: oauthError || null,
  });

  if (oauthError || !code) {
    return redirectToLogin(request, oauthError || "google_oauth_denied");
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
      headers: {
        "x-correlation-id": correlationId,
        "x-request-id": correlationId,
      },
    });

    if (!response.ok) {
      const detail = await response.text();
      console.error("oauth_callback_backend_failed", {
        correlationId,
        status: response.status,
        detailLength: detail.length,
      });
      return redirectToLogin(request, "google_oauth_failed");
    }

    const data = (await response.json()) as {
      user?: ProductDoorUser;
      mfa_required?: boolean;
    };
    if (data.mfa_required) {
      const login = publicAppUrl("/login", request);
      login.searchParams.set("mfa", "required");
      const pending = NextResponse.redirect(login);
      forwardBackendSetCookies(response, pending);
      return pending;
    }
    const user: ProductDoorUser = data.user ?? { is_superuser: false };
    const destination = resolvePostLoginPath(user, null);
    const nextResponse = NextResponse.redirect(publicAppUrl(destination, request));
    forwardBackendSetCookies(response, nextResponse);
    console.info("oauth_callback_completed", { correlationId, destination });
    return nextResponse;
  } catch (error) {
    console.error("oauth_callback_exception", {
      correlationId,
      error: error instanceof Error ? error.name : "unknown",
    });
    return redirectToLogin(request, "google_oauth_failed");
  }
}
